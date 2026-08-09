#!/usr/bin/env bash
set -Eeuo pipefail

repository=${GITHUB_REPOSITORY:-}
commit_sha=${GITHUB_SHA:-}
github_output=${GITHUB_OUTPUT:-}
release_created=${RELEASE_CREATED:-false}
release_tag_name=${RELEASE_TAG_NAME:-}
release_sha=${RELEASE_SHA:-}
manifest_path=${RELEASE_MANIFEST_PATH:-.release-please-manifest.json}
gh_bin=${RELEASE_GH_BIN:-gh}

die() {
  printf 'Release reconciliation: %s\n' "$1" >&2
  exit 1
}

write_tag() {
  printf 'release_tag=%s\n' "$1" >> "$github_output"
}

[[ $repository =~ ^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$ ]] || die 'GITHUB_REPOSITORY must be OWNER/REPO'
[[ $commit_sha =~ ^[0-9a-f]{40}$ ]] || die 'GITHUB_SHA must be a lowercase 40-hex SHA'
[[ -n $github_output ]] || die 'GITHUB_OUTPUT is required'
[[ $release_created == true || $release_created == false ]] || die 'RELEASE_CREATED must be true or false'
[[ -n $manifest_path ]] || die 'RELEASE_MANIFEST_PATH must not be empty'
[[ -n $gh_bin ]] || die 'RELEASE_GH_BIN must not be empty'

if [[ $release_created == true ]]; then
  [[ $release_tag_name =~ ^v[0-9]+\.[0-9]+\.[0-9]+$ ]] || die 'RELEASE_TAG_NAME must be an exact vX.Y.Z tag'
  [[ $release_sha == "$commit_sha" ]] || die 'new release SHA does not match GITHUB_SHA'
  write_tag "$release_tag_name"
  exit 0
fi

version=$(jq -er '.["."] | select(type == "string")' "$manifest_path") || die 'release manifest must contain a root version string'
[[ $version =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] || die 'root release manifest version must be exact X.Y.Z SemVer'
release_tag="v$version"

release_error=$(mktemp)
trap 'rm -f "$release_error"' EXIT
if existing_tag=$("$gh_bin" api "repos/$repository/releases/tags/$release_tag" --jq .tag_name 2>"$release_error"); then
  :
elif grep -Eq '\(HTTP 404\)' "$release_error"; then
  write_tag ''
  exit 0
else
  die 'could not query existing GitHub Release'
fi
[[ $existing_tag == "$release_tag" ]] || die 'GitHub Release response has an invalid tag identity'

resolved_sha=$(
  "$gh_bin" api "repos/$repository/commits/$release_tag" --jq .sha
) || die 'could not resolve release tag commit'
[[ $resolved_sha =~ ^[0-9a-f]{40}$ ]] || die 'resolved release commit must be a lowercase 40-hex SHA'

if [[ $resolved_sha == "$commit_sha" ]]; then
  write_tag "$release_tag"
else
  write_tag ''
fi
