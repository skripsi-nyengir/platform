#!/usr/bin/env bash
set -Eeuo pipefail

repository=${GATE_REPOSITORY:-${GITHUB_REPOSITORY:-}}
commit_sha=${GATE_COMMIT_SHA:-${GITHUB_SHA:-}}
workflow_path=${GATE_WORKFLOW_PATH:-ci-release-deploy.yml}
timeout_seconds=${GATE_TIMEOUT_SECONDS:-900}
poll_seconds=${GATE_POLL_SECONDS:-15}
gh_bin=${GATE_GH_BIN:-gh}
github_output=${GITHUB_OUTPUT:-}

die() {
  printf 'Merged PR unit gate: %s\n' "$1" >&2
  exit 1
}

[[ $repository =~ ^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$ ]] || die 'GATE_REPOSITORY must be OWNER/REPO'
[[ $commit_sha =~ ^[0-9a-f]{40}$ ]] || die 'GATE_COMMIT_SHA must be a lowercase 40-hex SHA'
[[ -n $workflow_path ]] || die 'GATE_WORKFLOW_PATH must not be empty'
[[ $timeout_seconds =~ ^[0-9]+$ ]] || die 'GATE_TIMEOUT_SECONDS must be a non-negative integer'
[[ $poll_seconds =~ ^[0-9]+$ ]] || die 'GATE_POLL_SECONDS must be a non-negative integer'
[[ -n $gh_bin ]] || die 'GATE_GH_BIN must not be empty'
[[ -n $github_output ]] || die 'GITHUB_OUTPUT is required'

pulls_json=$("$gh_bin" api "repos/$repository/commits/$commit_sha/pulls")
matching_prs=$(jq -ce --arg commit "$commit_sha" '
  [ .[]
    | select(
        .state == "closed"
        and .merged_at != null
        and .base.ref == "main"
        and .merge_commit_sha == $commit
      )
  ]
' <<<"$pulls_json") || die 'associated pull request response is not valid JSON'

[[ $(jq 'length' <<<"$matching_prs") -eq 1 ]] || die 'commit must have exactly one merged pull request targeting main'
pr_number=$(jq -er '.[0].number | select(type == "number" and . > 0 and floor == .)' <<<"$matching_prs") || die 'pull request number must be a positive integer'
pr_head_sha=$(jq -er '.[0].head.sha | select(type == "string" and test("^[0-9a-f]{40}$"))' <<<"$matching_prs") || die 'pull request head SHA must be lowercase 40-hex'

case "$workflow_path" in
  .github/workflows/*) expected_run_path=$workflow_path ;;
  *) expected_run_path=".github/workflows/$workflow_path" ;;
esac

started_at=$SECONDS
workflow_run_id=
while :; do
  runs_json=$("$gh_bin" api "repos/$repository/actions/workflows/$workflow_path/runs?event=pull_request&head_sha=$pr_head_sha&per_page=100")
  latest_run=$(jq -ce --arg head "$pr_head_sha" --arg path "$expected_run_path" '
    [ .workflow_runs[]
      | select(.event == "pull_request" and .head_sha == $head and .path == $path)
    ]
    | sort_by(.created_at, .id)
    | last // null
  ' <<<"$runs_json") || die 'workflow runs response is not valid JSON'

  if [[ $latest_run != null ]]; then
    run_status=$(jq -er '.status | select(type == "string")' <<<"$latest_run") || die 'latest workflow run has an invalid status'
    if [[ $run_status == completed ]]; then
      run_conclusion=$(jq -er '.conclusion | select(type == "string")' <<<"$latest_run") || die 'completed workflow run has an invalid conclusion'
      [[ $run_conclusion == success ]] || die "latest workflow run concluded $run_conclusion"
      workflow_run_id=$(jq -er '.id | select(type == "number" and . > 0 and floor == .)' <<<"$latest_run") || die 'successful workflow run ID must be a positive integer'
      break
    fi
  fi

  ((SECONDS - started_at < timeout_seconds)) || die 'timed out waiting for a successful PR unit workflow run'
  sleep "$poll_seconds"
done

artifact_dir=$(mktemp -d)
trap 'rm -rf "$artifact_dir"' EXIT
"$gh_bin" run download "$workflow_run_id" -R "$repository" -n "pr-unit-gate-$pr_number" -D "$artifact_dir"

mapfile -t evidence_files < <(find "$artifact_dir" -type f -name pr-unit-gate.json -print)
[[ ${#evidence_files[@]} -eq 1 ]] || die 'artifact must contain exactly one pr-unit-gate.json'
evidence_file=${evidence_files[0]}

jq -e \
  --argjson pr_number "$pr_number" \
  --arg head_sha "$pr_head_sha" \
  --argjson workflow_run_id "$workflow_run_id" '
    (keys | sort) == ["head_sha", "pr_number", "result", "schema", "workflow_run_id"]
    and .schema == 1
    and (.schema | type) == "number"
    and .pr_number == $pr_number
    and (.pr_number | type) == "number"
    and .head_sha == $head_sha
    and (.head_sha | type) == "string"
    and .workflow_run_id == $workflow_run_id
    and (.workflow_run_id | type) == "number"
    and .result == "success"
    and (.result | type) == "string"
  ' "$evidence_file" >/dev/null || die 'PR unit gate evidence failed schema or identity validation'

{
  printf 'pr_number=%s\n' "$pr_number"
  printf 'pr_head_sha=%s\n' "$pr_head_sha"
  printf 'pr_workflow_run_id=%s\n' "$workflow_run_id"
} >> "$github_output"
