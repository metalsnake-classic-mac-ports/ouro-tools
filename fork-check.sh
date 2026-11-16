#!/bin/sh
# Monthly check of the macemu forks (see FORK-CHECK.md).
#
#   fork-check.sh changed    list forks whose branches moved since fork-heads.tsv
#                            (new forks, new or moved branches), one line each
#   fork-check.sh snapshot   rewrite fork-heads.tsv with the current branch heads
#   fork-check.sh ahead      every branch in fork-heads.tsv that has commits its base
#                            lacks: date of its head, commits ahead, commits behind,
#                            repository, branch - newest first. The base is
#                            kanjitalk755/macemu master, for PocketShaver forks
#                            carbjo/PocketShaver master. Asks GitHub's compare API,
#                            clones nothing (about two calls per branch)
#   fork-check.sh due        print "due since DATE" when the last check in
#                            FORK-CHECK.md is more than a month old, else nothing
#   fork-check.sh hook       Claude Code SessionStart hook: the same as a context
#                            reminder, only in sessions under the ports folder
#
# Watched: every fork of kanjitalk755/macemu, the PocketShaver family (carbjo and
# its forks) and ouro-macemu's sources. Needs gh (logged in) and git.
set -e
# Where the script was started and its own path, taken before the cd below changes $PWD
# and makes a relative $0 useless. The hook falls back to the first when Claude Code
# doesn't set CLAUDE_PROJECT_DIR.
started_in=$PWD
self="$(cd "$(dirname "$0")" && pwd)/$(basename "$0")"
cd "$(dirname "$0")"
HEADS=fork-heads.tsv

repos() {
    {
        echo kanjitalk755/macemu
        gh api --paginate 'repos/kanjitalk755/macemu/forks?per_page=100' --jq '.[].full_name'
        echo carbjo/PocketShaver
        gh api --paginate 'repos/carbjo/PocketShaver/forks?per_page=100' --jq '.[].full_name'
        echo Ploos-AS/MacSandbox
    } | grep -v '^metalsnake-classic-mac-ports/' | sort -u
}

current() {   # repo <TAB> branch <TAB> sha, for every branch of every watched repo
    repos | while read -r r; do
        git ls-remote --heads "https://github.com/$r.git" 2>/dev/null |
            sed "s|^\([0-9a-f]*\)\trefs/heads/\(.*\)|$r\t\2\t\1|"
    done | sort
}

case "$1" in
snapshot)
    current > "$HEADS.new" && mv "$HEADS.new" "$HEADS"
    echo "$(wc -l < "$HEADS" | tr -d ' ') branches in $HEADS"
    ;;
changed)
    [ -f "$HEADS" ] || { echo "no $HEADS yet: run snapshot" >&2; exit 1; }
    current > "$HEADS.now"
    # lines that are new or changed, reduced to the repository and branch
    comm -13 "$HEADS" "$HEADS.now" | cut -f1,2 | while IFS="$(printf '\t')" read -r r b; do
        old=$(awk -F'\t' -v r="$r" -v b="$b" '$1==r && $2==b {print $3}' "$HEADS")
        echo "$r $b ${old:-new}"
    done
    rm -f "$HEADS.now"
    ;;
ahead)
    [ -f "$HEADS" ] || { echo "no $HEADS yet: run snapshot" >&2; exit 1; }
    # One line "repository branch sha base" per branch (branch names contain no
    # spaces), then eight compare calls at a time. The head is given by its sha,
    # which GitHub resolves across the fork network, so branch names with "/"
    # need no escaping.
    while IFS="$(printf '\t')" read -r repository branch sha; do
        case "$repository" in
        carbjo/PocketShaver) base=kanjitalk755/macemu ;;
        */PocketShaver)      base=carbjo/PocketShaver ;;
        *)                   base=kanjitalk755/macemu ;;
        esac
        echo "$repository $branch $sha $base"
    done < "$HEADS" |
    xargs -n 4 -P 8 sh -c '
        repository=$1 branch=$2 sha=$3 base=$4
        compare() {
            gh api "repos/$base/compare/master...$1?per_page=1" \
                --jq "\"\(.ahead_by) \(.behind_by)\"" 2>/dev/null
        }
        # GitHub does not find every sha in the network (404); then name the
        # head as owner:repository:branch, with "/" in the branch escaped.
        owner_head="$(echo "$repository" | tr / :):$(echo "$branch" | sed "s|/|%2F|g")"
        counts=$(compare "$sha") || counts=$(compare "$owner_head") || {
            printf "?\t?\t?\t%s\t%s\t(compare failed)\n" "$repository" "$branch"; exit 0; }
        set -- $counts
        ahead=$1 behind=$2
        [ "$ahead" -gt 0 ] || exit 0
        date=$(gh api "repos/$repository/commits/$sha" --jq ".commit.committer.date[:10]" 2>/dev/null || echo "?")
        printf "%s\t%s\t%s\t%s\t%s\n" "$date" "$ahead" "$behind" "$repository" "$branch"
    ' sh | sort -r
    ;;
due)
    last=$(sed -n 's/^Last check: \([0-9-]*\).*/\1/p' FORK-CHECK.md | head -1)
    [ -n "$last" ] || { echo "due (no date in FORK-CHECK.md)"; exit 0; }
    limit=$(date -v-1m +%Y-%m-%d 2>/dev/null || date -d '1 month ago' +%Y-%m-%d)
    if [ "$last" \< "$limit" ] || [ "$last" = "$limit" ]; then echo "due since $last"; fi
    ;;
hook)
    # Claude Code SessionStart hook: in a session under the ports folder (the
    # parent of this one), add a reminder to the context when the check is due.
    case "${CLAUDE_PROJECT_DIR:-$started_in}/" in
    "$(cd .. && pwd)"/*) ;;
    *) exit 0 ;;
    esac
    msg=$("$self" due)
    [ -n "$msg" ] || exit 0
    printf '{"hookSpecificOutput":{"hookEventName":"SessionStart","additionalContext":"The monthly macemu fork check is %s. Tell the user and offer to run it now; how: %s/FORK-CHECK.md."}}\n' \
        "$msg" "$(pwd)"
    ;;
*)
    echo "usage: fork-check.sh changed|snapshot|due|hook" >&2; exit 2
    ;;
esac
