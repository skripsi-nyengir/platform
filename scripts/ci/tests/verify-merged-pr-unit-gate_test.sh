#!/usr/bin/env bash
set -Eeuo pipefail

root_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)
gate="$root_dir/scripts/ci/verify-merged-pr-unit-gate.sh"
commit=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
head_sha=bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb
run_id=123
pr_number=42
pass_count=0
fail_count=0

fail() {
  printf 'not ok - %s\n' "$1" >&2
  fail_count=$((fail_count + 1))
}

pass() {
  printf 'ok - %s\n' "$1"
  pass_count=$((pass_count + 1))
}

make_fake_gh() {
  local path=$1
  cat > "$path" <<'FAKE_GH'
#!/usr/bin/env bash
set -Eeuo pipefail

commit=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
head_sha=bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb
pr_number=42
run_id=123

if [[ $1 == api && $2 == "repos/example/project/commits/$commit/pulls" ]]; then
  case "$TEST_CASE" in
    no_pr) printf '[]\n' ;;
    unmerged) jq -nc --arg commit "$commit" --arg head "$head_sha" '[{number:42,state:"closed",merged_at:null,base:{ref:"main"},merge_commit_sha:$commit,head:{sha:$head}}]' ;;
    wrong_base) jq -nc --arg commit "$commit" --arg head "$head_sha" '[{number:42,state:"closed",merged_at:"2026-08-09T00:00:00Z",base:{ref:"dev"},merge_commit_sha:$commit,head:{sha:$head}}]' ;;
    ambiguous) jq -nc --arg commit "$commit" --arg head "$head_sha" '[{number:42,state:"closed",merged_at:"2026-08-09T00:00:00Z",base:{ref:"main"},merge_commit_sha:$commit,head:{sha:$head}},{number:43,state:"closed",merged_at:"2026-08-09T00:01:00Z",base:{ref:"main"},merge_commit_sha:$commit,head:{sha:"cccccccccccccccccccccccccccccccccccccccc"}}]' ;;
    *) jq -nc --arg commit "$commit" --arg head "$head_sha" '[{number:42,state:"closed",merged_at:"2026-08-09T00:00:00Z",base:{ref:"main"},merge_commit_sha:$commit,head:{sha:$head}}]' ;;
  esac
elif [[ $1 == api && $2 == "repos/example/project/actions/workflows/ci-release-deploy.yml/runs?event=pull_request&head_sha=$head_sha&per_page=100" ]]; then
  case "$TEST_CASE" in
    no_run) printf '{"workflow_runs":[]}\n' ;;
    active_run) jq -nc --arg head "$head_sha" '{workflow_runs:[{id:123,event:"pull_request",head_sha:$head,path:".github/workflows/ci-release-deploy.yml",status:"in_progress",conclusion:null,created_at:"2026-08-09T00:00:00Z"}]}' ;;
    failed_run) jq -nc --arg head "$head_sha" '{workflow_runs:[{id:123,event:"pull_request",head_sha:$head,path:".github/workflows/ci-release-deploy.yml",status:"completed",conclusion:"failure",created_at:"2026-08-09T00:00:00Z"}]}' ;;
    cancelled_run) jq -nc --arg head "$head_sha" '{workflow_runs:[{id:123,event:"pull_request",head_sha:$head,path:".github/workflows/ci-release-deploy.yml",status:"completed",conclusion:"cancelled",created_at:"2026-08-09T00:00:00Z"}]}' ;;
    *) jq -nc --arg head "$head_sha" '{workflow_runs:[{id:122,event:"pull_request",head_sha:$head,path:".github/workflows/ci-release-deploy.yml",status:"completed",conclusion:"failure",created_at:"2026-08-08T00:00:00Z"},{id:123,event:"pull_request",head_sha:$head,path:".github/workflows/ci-release-deploy.yml",status:"completed",conclusion:"success",created_at:"2026-08-09T00:00:00Z"}]}' ;;
  esac
elif [[ $1 == run && $2 == download ]]; then
  [[ $3 == "$run_id" ]]
  shift 3
  destination=
  while (($#)); do
    case "$1" in
      -D) destination=$2; shift 2 ;;
      -n) [[ $2 == "pr-unit-gate-$pr_number" ]]; shift 2 ;;
      -R) [[ $2 == example/project ]]; shift 2 ;;
      *) exit 90 ;;
    esac
  done
  mkdir -p "$destination"
  case "$TEST_CASE" in
    malformed_evidence) printf '{not json\n' > "$destination/pr-unit-gate.json" ;;
    stale_head) jq -n --arg head cccccccccccccccccccccccccccccccccccccccc '{schema:1,pr_number:42,head_sha:$head,workflow_run_id:123,result:"success"}' > "$destination/pr-unit-gate.json" ;;
    wrong_pr) jq -n --arg head "$head_sha" '{schema:1,pr_number:43,head_sha:$head,workflow_run_id:123,result:"success"}' > "$destination/pr-unit-gate.json" ;;
    wrong_run) jq -n --arg head "$head_sha" '{schema:1,pr_number:42,head_sha:$head,workflow_run_id:122,result:"success"}' > "$destination/pr-unit-gate.json" ;;
    non_success_result) jq -n --arg head "$head_sha" '{schema:1,pr_number:42,head_sha:$head,workflow_run_id:123,result:"failure"}' > "$destination/pr-unit-gate.json" ;;
    extra_key) jq -n --arg head "$head_sha" '{schema:1,pr_number:42,head_sha:$head,workflow_run_id:123,result:"success",extra:true}' > "$destination/pr-unit-gate.json" ;;
    missing_key) jq -n --arg head "$head_sha" '{schema:1,pr_number:42,head_sha:$head,result:"success"}' > "$destination/pr-unit-gate.json" ;;
    wrong_types) jq -n --arg head "$head_sha" '{schema:"1",pr_number:"42",head_sha:$head,workflow_run_id:"123",result:"success"}' > "$destination/pr-unit-gate.json" ;;
    *) jq -n --arg head "$head_sha" '{schema:1,pr_number:42,head_sha:$head,workflow_run_id:123,result:"success"}' > "$destination/pr-unit-gate.json" ;;
  esac
else
  printf 'unexpected fake gh invocation:' >&2
  printf ' %q' "$@" >&2
  printf '\n' >&2
  exit 91
fi
FAKE_GH
  chmod +x "$path"
}

run_case() {
  local name=$1
  local expected_status=$2
  local tmp_dir output_file status actual_output expected_output
  tmp_dir=$(mktemp -d)
  output_file="$tmp_dir/github-output"
  : > "$output_file"
  make_fake_gh "$tmp_dir/gh"

  status=0
  TEST_CASE=$name \
    GATE_REPOSITORY=example/project \
    GATE_COMMIT_SHA=$commit \
    GATE_TIMEOUT_SECONDS=0 \
    GATE_POLL_SECONDS=0 \
    GATE_GH_BIN="$tmp_dir/gh" \
    GITHUB_OUTPUT="$output_file" \
    "$gate" >"$tmp_dir/stdout" 2>"$tmp_dir/stderr" || status=$?

  if [[ $expected_status == success ]]; then
    expected_output=$(printf 'pr_number=%s\npr_head_sha=%s\npr_workflow_run_id=%s' "$pr_number" "$head_sha" "$run_id")
    actual_output=$(cat "$output_file")
    if [[ $status -eq 0 && $actual_output == "$expected_output" ]]; then
      pass "$name"
    else
      fail "$name (status=$status output=$(printf %q "$actual_output"))"
      sed 's/^/  stderr: /' "$tmp_dir/stderr" >&2
    fi
  elif [[ $status -ne 0 && ! -s $output_file ]]; then
    pass "$name"
  else
    fail "$name (expected failure with empty output; status=$status)"
  fi

  rm -rf "$tmp_dir"
}

run_case valid success
run_case no_pr failure
run_case unmerged failure
run_case wrong_base failure
run_case ambiguous failure
run_case no_run failure
run_case active_run failure
run_case failed_run failure
run_case cancelled_run failure
run_case malformed_evidence failure
run_case stale_head failure
run_case wrong_pr failure
run_case wrong_run failure
run_case non_success_result failure
run_case extra_key failure
run_case missing_key failure
run_case wrong_types failure

printf '%d passed; %d failed\n' "$pass_count" "$fail_count"
((fail_count == 0))
