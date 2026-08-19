# Git Workflow Guide

This file documents the recommended Git commands and workflow for working on the `Homebank_Converter` repository.

## 1) Sync your fork with the original `master`

Use this when you want your local `master` to match the upstream repository:

```bash
# add upstream once if not already configured
git remote add upstream https://github.com/Pom2terre/Homebank_Converter.git

# update remote references
git fetch upstream

# switch to local master
git checkout master

# fast-forward local master from upstream/master
git pull upstream master
```

If you also want your forked `origin/master` to match:

```bash
git push origin master
```

---

## 2) Create a clean new branch for new work

Always start a new branch from the updated `master`:

```bash
git checkout master
git pull upstream master
git checkout -b feature/enhance-tests-battery
```

Work in this branch and keep commits focused on one feature or fix.

---

## 3) Stage, commit, and push local changes

After editing files, run:

```bash
git add .
git commit -m "Enhance tests battery"
git push -u origin feature/enhance-tests-battery
```

This creates the branch on GitHub and links your local branch to the remote branch.

---

## 4) Open a Pull Request

### Option A: GitHub web
1. Open your fork on GitHub.
2. Switch to `feature/enhance-tests-battery`.
3. Click `Compare & pull request`.
4. Set base to `master`.
5. Enter a title and description.
6. Create PR.

### Option B: GitHub CLI

```bash
gh pr create --base master --head YOUR_USERNAME:feature/enhance-tests-battery \
  --title "Enhance tests battery" \
  --body "Summary:\n- Improve test coverage for converter detection and PDF extraction\n- Add new unit tests\n\nValidation:\n- python -m unittest tests.test_select_and_convert"
```

Replace `YOUR_USERNAME` with your GitHub username.

---

## 5) Keep your branch in sync with `master`

If `master` changes while you are working, rebase or merge the updates:

```bash
git checkout feature/enhance-tests-battery
git fetch upstream
git rebase upstream/master
# resolve conflicts if necessary
git push --force-with-lease
```

If you prefer merge instead of rebase:

```bash
git checkout feature/enhance-tests-battery
git pull --rebase upstream master
git push --force-with-lease
```

---

## 6) Recovery and useful commands

### Check status
```bash
git status
```

### See recent commits
```bash
git log --oneline --decorate --graph -n 10
```

### Compare current branch with master
```bash
git diff master..feature/enhance-tests-battery
```

### Stash local work temporarily
```bash
git stash
git stash pop
```

### Undo local changes before commit
```bash
git checkout -- <file>
```

### Undo last commit, keep changes staged
```bash
git reset --soft HEAD~1
```

### Undo last commit and unstage changes
```bash
git reset --mixed HEAD~1
```

### Remove untracked files safely
```bash
git clean -fd
```

---

## 7) Special note on `origin/working`

- `working` is your local branch.
- `origin/working` is the remote copy of that branch on GitHub.
- `origin/working` is useful for backup, collaboration, and PRs.

If `working` has already been merged, start a new branch for new work rather than continuing on the same branch.

---

## 8) When to create a new branch

Create a new branch for every new feature, fix, or test enhancement if:
- the old branch has already been merged,
- the new changes are unrelated to the previous PR,
- you want a clean history and easy review.

---

## 9) Recommended new branch workflow

```bash
git checkout master
git pull upstream master
git checkout -b feature/short-descriptive-name
git add .
git commit -m "Your commit message"
git push -u origin feature/short-descriptive-name
```

---

## 10) Notes on `.gitignore`

- `.gitignore` prevents new files from being tracked.
- It does not remove files already tracked by Git.
- To stop tracking already committed files:

```bash
git rm --cached path/to/file
```

- Always ignore build artifacts such as:

```text
__pycache__/
*.pyc
```
