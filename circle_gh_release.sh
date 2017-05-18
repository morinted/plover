#!/bin/bash
set -e
github_release="$(python3 -m utils.download 'https://github.com/aktau/github-release/releases/download/v0.7.2/darwin-amd64-github-release.tar.bz2' '16d40bcb4de7e29055789453f0d5fdbf1bfd3b49')"
tar xvjf "$github_release"
./bin/darwin/amd64/github-release release --user morinted --repo plover --tag "$(git describe --tags)" --draft
./bin/darwin/amd64/github-release upload --user morinted --repo plover --tag "$(git describe --tags)" --file "$(find $CIRCLE_ARTIFACTS/*.dmg)" --name "$(basename $(find $CIRCLE_ARTIFACTS/*.dmg))"
