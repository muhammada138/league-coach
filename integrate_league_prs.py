import subprocess
import json
import os

repo = "muhammada138/league-coach"
author_name = "Muhammad Abdullah"
author_email = "128553002+muhammada138@users.noreply.github.com"

def run(cmd):
    print(f"Running: {cmd}")
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        return (result.stdout or "").strip(), result.returncode, (result.stderr or "").strip()
    except Exception as e:
        print(f"Exec Exception: {e}")
        return "", 1, str(e)

def main():
    print("Fetching open PRs...")
    prs_json, code, err = run(f"gh pr list --repo {repo} --json number,title,headRefName")
    if not prs_json:
        print("No open PRs found.")
        return
    
    prs = json.loads(prs_json)
    print(f"Found {len(prs)} PRs.")

    run("git checkout master")

    for pr in prs:
        num = pr['number']
        title = pr['title'].replace('"', "'")
        branch = pr['headRefName']
        
        print(f"\n--- Processing PR #{num}: {title} ---")
        
        # Reset any mess
        run("git merge --abort")
        run("git reset --hard")
        
        # Pull branch
        run(f"gh pr checkout {num}")
        run("git checkout master")
        
        # Squash merge with "theirs" strategy to resolve most conflicts automatically
        print(f"Squash merging {branch} with 'theirs' strategy...")
        run(f"git merge {branch} --squash -X theirs")
        
        # Check if there are still conflicts
        status, _, _ = run("git status")
        if "unmerged paths" in status.lower() or "conflict" in status.lower():
            print("Conflict detected! Forcing 'theirs' on all files...")
            run("git checkout --theirs .")
            run("git add .")

        # Commit
        with open("temp_msg.txt", "w", encoding="utf-8") as f:
            f.write(f"{title}\n\nMerged PR #{num} via local squash to preserve unified contributor history.")
        
        out, code, err = run(f'git commit --author="{author_name} <{author_email}>" -F temp_msg.txt')
        if code != 0 and "nothing to commit" not in out.lower():
            print(f"Commit failed: {err}")
            continue

        # Close PR
        print(f"Closing PR #{num} on GitHub...")
        run(f"gh pr close {num} --repo {repo}")
        
        # Force push master immediately to save progress
        run("git push origin master --force")
        
        if os.path.exists("temp_msg.txt"):
            os.remove("temp_msg.txt")

    print("\nFinal Cleanup...")
    # Clean up remote branches
    branches_raw, _, _ = run("git branch -r")
    for b in branches_raw.split("\n"):
        clean_b = b.strip().replace("origin/", "")
        if clean_b and clean_b != "master" and "HEAD" not in clean_b:
            run(f"git push origin --delete {clean_b}")

if __name__ == "__main__":
    main()
