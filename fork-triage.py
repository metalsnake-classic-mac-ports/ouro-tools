"""Triage the fork branches that `fork-check.sh ahead` lists.

Fetches every listed branch without file contents into a scratch repository
(refs/f/owner__repo__branch), together with the two bases. For every branch it
lists the non-merge commits its base lacks (kanjitalk755 master, for PocketShaver
forks carbjo master), drops commits whose subject also exists upstream, and
drops commits that touch only paths outside our build (Unix/SDL Basilisk II and
SheepShaver on macOS arm64, no JIT). Prints the remaining commits, each subject
once, with the branches that carry it, newest first.

Usage:
    ./fork-check.sh ahead > ahead.tsv
    python3 -I fork-triage.py ahead.tsv SCRATCH_DIRECTORY > triage.txt

SCRATCH_DIRECTORY is created if missing; nothing in it is built or run.
"""
import re
import subprocess
import sys
from collections import defaultdict

ahead_file, repository_directory = sys.argv[1], sys.argv[2]


def git(*arguments, check=True):
    return subprocess.run(["git", "-C", repository_directory, *arguments],
                          capture_output=True, text=True, check=check).stdout


def fetch_everything():
    """Fetch the bases and every branch of the ahead list, blobless."""
    subprocess.run(["git", "init", "-q", repository_directory], check=True)
    for url, reference in [("https://github.com/kanjitalk755/macemu.git", "r/up-master"),
                           ("https://github.com/carbjo/PocketShaver.git", "r/carbjo-master")]:
        git("fetch", "-q", "--filter=blob:none", url, f"+master:refs/heads/{reference}")
    branches_of_repository = defaultdict(list)
    for line in open(ahead_file):
        columns = line.rstrip("\n").split("\t")
        if len(columns) >= 5:
            branches_of_repository[columns[3]].append(columns[4])
    for repository, branches in sorted(branches_of_repository.items()):
        refspecs = [f"+refs/heads/{branch}:refs/f/{repository.replace('/', '__')}__{branch.replace('/', '__')}"
                    for branch in branches]
        result = subprocess.run(["git", "-C", repository_directory, "fetch", "-q", "--filter=blob:none",
                                 f"https://github.com/{repository}.git", *refspecs],
                                capture_output=True, text=True)
        if result.returncode != 0:
            # A branch deleted since the snapshot fails the whole fetch: report it.
            print(f"# fetch failed: {repository}: {result.stderr.strip().splitlines()[-1:]}", file=sys.stderr)


fetch_everything()


# Paths that never reach our build. A commit is dropped only when *every*
# path it touches matches one of these.
IGNORED_PATH_PATTERNS = [re.compile(pattern, re.IGNORECASE) for pattern in [
    r"/Windows/", r"^Windows/", r"/AmigaOS/", r"/BeOS/", r"/Irix/", r"/dummy/",
    r"android", r"/ios/", r"\bios\b", r"iOS", r"PocketShaver", r"\.swift$",
    r"\.xcodeproj/", r"\.xcworkspace/", r"\.xcassets/", r"\.storyboard$", r"\.xib$",
    r"\.plist$", r"\.entitlements$", r"\.icns$", r"\.png$", r"\.jpg$", r"\.nib/",
    r"gfxaccel", r"metal", r"\.metal$", r"rave", r"drawsprocket", r"/dsp_",
    r"/compiler/", r"/jit", r"jit[_.]", r"_jit", r"dyngen", r"osxguest", r"/SFL/",
    r"^\.github/", r"\.yml$", r"\.yaml$", r"\.md$", r"README", r"TODO", r"ChangeLog",
    r"NEWS", r"COPYING", r"\.txt$", r"^docs?/", r"/docs?/", r"\.html$",
    r"thirdparty/", r"^tools/", r"^tests?/", r"/tests?/", r"\.gitignore$",
    r"CMakeLists\.txt$", r"\.cmake$", r"Makefile\.(mingw|win|vc)", r"\.vcxproj",
    r"\.sln$", r"\.rc$", r"_gtk", r"/GTK/", r"\.desktop$", r"\.spec$", r"flatpak",
    r"snap/", r"Dockerfile", r"\.sh$", r"\.bat$", r"\.ps1$", r"/NetBSD/", r"wscons",
    r"wayland", r"/Linux/", r"_linux", r"/Darwin/.*\.(xc|pb)", r"/emscripten/",
    r"infinite", r"/js/", r"\.js$", r"\.ts$", r"\.css$",
]]

upstream_subjects = set(git("log", "--format=%s", "r/up-master").splitlines())

commits = {}                          # sha -> (date, author, subject, paths)
branches_of_commit = defaultdict(list)
for reference in git("for-each-ref", "--format=%(refname)", "refs/f/").split():
    name = reference[len("refs/f/"):].replace("__", "/", 2)
    owner_repository = "/".join(name.split("/")[:2])
    is_pocketshaver_fork = (owner_repository.endswith("/PocketShaver")
                            and owner_repository != "carbjo/PocketShaver")
    base = "r/carbjo-master" if is_pocketshaver_fork else "r/up-master"
    log = git("log", "--no-merges", "--date=short", "--name-only",
              "--format=\x01%H\x02%ad\x02%an\x02%s", f"{base}..{reference}")
    for record in log.split("\x01")[1:]:
        header, _, path_block = record.partition("\n")
        sha, date, author, subject = header.split("\x02")
        paths = [line for line in path_block.splitlines() if line.strip()]
        commits[sha] = (date, author, subject, paths)
        branches_of_commit[sha].append(name)

kept = []
dropped_upstream_subject = dropped_paths = 0
for sha, (date, author, subject, paths) in commits.items():
    if subject in upstream_subjects:
        dropped_upstream_subject += 1
        continue
    relevant_paths = [path for path in paths
                      if not any(pattern.search(path) for pattern in IGNORED_PATH_PATTERNS)]
    if not relevant_paths:
        dropped_paths += 1
        continue
    kept.append((date, sha, author, subject, relevant_paths))

# The same change often sits in several forks under different shas: group by subject.
by_subject = defaultdict(list)
for entry in kept:
    by_subject[(entry[3], entry[2])].append(entry)

print(f"# commits: {len(commits)}, same subject upstream: {dropped_upstream_subject}, "
      f"only ignored paths: {dropped_paths}, kept: {len(kept)}, distinct: {len(by_subject)}")
for (subject, author), entries in sorted(by_subject.items(), key=lambda item: max(e[0] for e in item[1]), reverse=True):
    date, sha, _, _, relevant_paths = max(entries)
    carriers = sorted({branch for entry in entries for branch in branches_of_commit[entry[1]]})
    print(f"{date} {sha[:8]} {author}: {subject}")
    print(f"    in: {', '.join(carriers[:4])}{' +' + str(len(carriers) - 4) if len(carriers) > 4 else ''}")
    print(f"    paths: {', '.join(relevant_paths[:6])}{' ...' if len(relevant_paths) > 6 else ''}")
