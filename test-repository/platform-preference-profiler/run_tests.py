"""Automated tests for platform-preference-profiler."""

import json
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
PROFILER_DIR = PROJECT_ROOT / "platform-preference-profiler"
TEST_FIXTURE = PROFILER_DIR / "test" / "fixtures" / "job1"


def run_profiler(force: bool = True) -> int:
    """Run the profiler and return exit code."""
    cmd = [
        sys.executable,
        str(PROFILER_DIR / "main.py"),
        "--job-dir", str(TEST_FIXTURE),
    ]
    if force:
        cmd.append("--force")
    
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=str(PROJECT_ROOT))
    print(result.stdout)
    if result.stderr:
        print("STDERR:", result.stderr)
    return result.returncode


def validate_profile(platform: str) -> bool:
    """Validate a generated profile file."""
    profile_path = PROJECT_ROOT / ".data" / "profiles" / f"{platform}_profile.json"
    
    if not profile_path.exists():
        print(f"❌ Profile not found: {profile_path}")
        return False
    
    profile = json.loads(profile_path.read_text(encoding="utf-8"))
    
    required_fields = [
        "pf", "gen_at", "v", "conf", "s_cnt", "s_ids",
        "topic", "lang", "vis", "struct", "forbid"
    ]
    
    missing = [f for f in required_fields if f not in profile]
    if missing:
        print(f"❌ {platform} profile missing fields: {missing}")
        return False
    
    # Validate types
    if not isinstance(profile["conf"], (int, float)):
        print(f"❌ {platform} conf must be numeric")
        return False
    
    if not 0 <= profile["conf"] <= 1:
        print(f"❌ {platform} conf must be between 0 and 1")
        return False
    
    if not isinstance(profile["struct"], list):
        print(f"❌ {platform} struct must be array")
        return False
    
    # Validate platform identifier
    if profile["pf"] != platform:
        print(f"❌ {platform} profile has wrong pf: {profile['pf']}")
        return False
    
    print(f"✅ {platform} profile valid (conf={profile['conf']}, samples={profile['s_cnt']})")
    return True


def validate_index_file() -> bool:
    """Validate the index file."""
    index_path = TEST_FIXTURE / "platform-preference-profiler.json"
    
    if not index_path.exists():
        print(f"❌ Index file not found: {index_path}")
        return False
    
    index = json.loads(index_path.read_text(encoding="utf-8"))
    
    required_fields = ["cid", "jid", "sample_root", "profile_root", "gen_at", "profiles"]
    missing = [f for f in required_fields if f not in index]
    if missing:
        print(f"❌ Index file missing fields: {missing}")
        return False
    
    platforms = ["xhs", "douyin", "wechat"]
    if len(index.get("profiles", [])) != len(platforms):
        print(f"❌ Index should have {len(platforms)} profiles, got {len(index.get('profiles', []))}")
        return False
    
    # Validate each profile entry
    for entry in index["profiles"]:
        if "pf" not in entry:
            print(f"❌ Profile entry missing 'pf' field")
            return False
        if entry["pf"] not in platforms:
            print(f"❌ Unknown platform in index: {entry['pf']}")
            return False
    
    print(f"✅ Index file valid ({len(index['profiles'])} platforms)")
    return True


def validate_samples() -> bool:
    """Validate sample files exist and have correct format."""
    samples_dir = PROJECT_ROOT / ".data" / "samples"
    platforms = ["xhs", "douyin", "wechat"]
    all_valid = True
    
    for platform in platforms:
        platform_dir = samples_dir / platform
        if not platform_dir.exists():
            print(f"❌ Sample directory not found: {platform_dir}")
            all_valid = False
            continue
        
        sample_files = list(platform_dir.glob("*.json"))
        if len(sample_files) < 3:
            print(f"⚠️  {platform} has only {len(sample_files)} samples (recommended: ≥3)")
        
        for sample_file in sample_files:
            try:
                sample = json.loads(sample_file.read_text(encoding="utf-8"))
                required = ["sample_id", "platform", "title", "body", "metrics"]
                missing = [f for f in required if f not in sample]
                if missing:
                    print(f"❌ {sample_file.name}: missing {missing}")
                    all_valid = False
                else:
                    print(f"✅ {platform}/{sample_file.name}: {sample['title'][:30]}...")
            except Exception as e:
                print(f"❌ {sample_file.name}: failed to parse - {e}")
                all_valid = False
    
    return all_valid


def main():
    print("=" * 60)
    print("Platform Preference Profiler - Test Suite")
    print("=" * 60)
    
    # Step 1: Validate samples
    print("\n[1/4] Validating samples...")
    if not validate_samples():
        print("\n⚠️  Some samples are invalid, but continuing...")
    
    # Step 2: Run profiler
    print("\n[2/4] Running profiler...")
    exit_code = run_profiler(force=True)
    if exit_code != 0:
        print("❌ Profiler failed")
        sys.exit(1)
    
    # Step 3: Validate profiles
    print("\n[3/4] Validating profiles...")
    platforms = ["xhs", "douyin", "wechat"]
    all_valid = True
    for platform in platforms:
        if not validate_profile(platform):
            all_valid = False
    
    if not all_valid:
        print("\n❌ Some profiles are invalid")
        sys.exit(1)
    
    # Step 4: Validate index file
    print("\n[4/4] Validating index file...")
    if not validate_index_file():
        sys.exit(1)
    
    print("\n" + "=" * 60)
    print("✅ All tests passed!")
    print("=" * 60)


if __name__ == "__main__":
    main()
