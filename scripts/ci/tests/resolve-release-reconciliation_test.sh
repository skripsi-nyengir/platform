#!/usr/bin/env bash
set -Eeuo pipefail

root_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)
resolver="$root_dir/scripts/ci/resolve-release-reconciliation.sh"
commit=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
other_commit=bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb
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
other_commit=bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb

if [[ $1 == api && $2 == repos/example/project/releases/tags/v1.2.3 && $3 == --jq && $4 == .tag_name ]]; then
  case "$TEST_CASE" in
    missing_release) printf 'gh: Not Found (HTTP 404)\n' >&2; exit 1 ;;
    api_error) printf 'gh: service unavailable (HTTP 503)\n' >&2; exit 1 ;;
    malformed_api) printf 'not-a-semver-tag\n' ;;
    *) printf 'v1.2.3\n' ;;
  esac
elif [[ $1 == api && $2 == repos/example/project/commits/v1.2.3 && $3 == --jq && $4 == .sha ]]; then
  case "$TEST_CASE" in
    rerun_exact) printf '%s\n' "$commit" ;;
    later_push|empty_release_created) printf '%s\n' "$other_commit" ;;
    *) exit 92 ;;
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
  local release_created=$2
  local expected_status=$3
  local expected_tag=${4-}
  local release_tag_name=${5-}
  local release_sha=${6-}
  local tmp_dir output_file status actual_output expected_output
  tmp_dir=$(mktemp -d)
  output_file="$tmp_dir/github-output"
  : > "$output_file"
  make_fake_gh "$tmp_dir/gh"

  case "$name" in
    malformed_version) printf '{".":"1.2"}\n' > "$tmp_dir/.release-please-manifest.json" ;;
    *) printf '{".":"1.2.3"}\n' > "$tmp_dir/.release-please-manifest.json" ;;
  esac

  status=0
  (
    cd "$tmp_dir"
    TEST_CASE=$name \
      GITHUB_REPOSITORY=example/project \
      GITHUB_SHA=$commit \
      GITHUB_OUTPUT="$output_file" \
      RELEASE_CREATED=$release_created \
      RELEASE_TAG_NAME=$release_tag_name \
      RELEASE_SHA=$release_sha \
      RELEASE_GH_BIN="$tmp_dir/gh" \
      "$resolver"
  ) >"$tmp_dir/stdout" 2>"$tmp_dir/stderr" || status=$?

  if [[ $expected_status == success ]]; then
    expected_output="release_tag=$expected_tag"
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

run_case new_release true success v1.2.3 v1.2.3 "$commit"
run_case rerun_exact false success v1.2.3
run_case later_push false success ''
run_case empty_release_created '' success ''
run_case missing_release false success ''
run_case api_error false failure
run_case malformed_version false failure
run_case malformed_api false failure
run_case mismatched_new_identity true failure '' v1.2.3 "$other_commit"

printf '%d passed; %d failed\n' "$pass_count" "$fail_count"
((fail_count == 0))
