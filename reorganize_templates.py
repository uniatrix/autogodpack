"""Script to reorganize template folders with cleaner names."""

import shutil
import os
from pathlib import Path

# Mapping: old_name -> new_name
FOLDER_MAPPING = {
    "screen_1_battle_selection": "battle_selection",
    "screen_2_battle_setup": "battle_setup",
    "battle_in_progress": "battle_in_progress",  # Keep as is
    "screen_3_victory": "result",
    "screen_4_5_6": "rewards",
    "screen_7": "summary",
    "screen_8": "popup_new_battle",
    "screen_defeat": "defeat",
    "screen_defeat_popup": "defeat_popup",
    "select_expansion": "expansion_selection",
}

def reorganize_templates(source_dir: Path, target_dir: Path):
    """Reorganize template folders."""
    print(f"Reorganizing templates from {source_dir} to {target_dir}")
    
    # Create target directory
    target_dir.mkdir(parents=True, exist_ok=True)
    
    # Copy and rename folders
    for old_name, new_name in FOLDER_MAPPING.items():
        old_path = source_dir / old_name
        new_path = target_dir / new_name
        
        if old_path.exists():
            if new_path.exists():
                print(f"  ⚠️  {new_name} already exists, skipping...")
            else:
                shutil.copytree(old_path, new_path)
                print(f"  ✅ {old_name} → {new_name}")
        else:
            print(f"  ❌ {old_name} not found, skipping...")
    
    print("\n✅ Template reorganization complete!")
    print(f"\nNew structure location: {target_dir}")

if __name__ == "__main__":
    # Use autogodpack/templates/battle as target (new structure)
    project_root = Path(__file__).parent
    source_dir = project_root / "src" / "templates" / "battle"
    target_dir = project_root / "autogodpack" / "templates" / "battle"
    
    if not source_dir.exists():
        print(f"❌ Source directory not found: {source_dir}")
        exit(1)
    
    reorganize_templates(source_dir, target_dir)
    
    print("\n📝 Next steps:")
    print("1. Update battle_bot.py to use new folder names")
    print("2. Update config.yaml if needed")
    print("3. Test the bot to ensure it works with new structure")






