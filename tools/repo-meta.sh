#!/usr/bin/env bash
# Set the GitHub repo's description, homepage, and topics from this file.
# Declarative: topics are replaced, not appended, so removing one here removes
# it on GitHub. Usage: tools/repo-meta.sh [owner/repo]
set -euo pipefail

REPO=${1:-aalpar/spitballing}

DESCRIPTION="Claude Code plugin for non-obvious ideas: a blind panel maps the obvious answers, then it samples the high-value, low-obviousness band and returns a ranked 3–5."
HOMEPAGE=""
TOPICS=(
  claude-code
  claude-code-plugin
  claude-skills
  llm
  creativity
  ideation
  idea-generation
  divergent-thinking
  brainstorming
)

gh repo edit "$REPO" --description "$DESCRIPTION" --homepage "$HOMEPAGE"

args=()
for t in "${TOPICS[@]}"; do args+=(-f "names[]=$t"); done
gh api -X PUT "repos/$REPO/topics" "${args[@]}" --silent

gh repo view "$REPO" --json description,homepageUrl,repositoryTopics \
  --jq '"description: \(.description)\nhomepage:    \(.homepageUrl)\ntopics:      \([.repositoryTopics[].name] | join(", "))"'
