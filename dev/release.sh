#!/usr/bin/env bash
# PyPi releases are automatically handled by github actions - this script simply builds & uploads a tag.
set -e
git checkout master
printf "Enter the version number: "
read -r VERSION
printf '\nEnsuring version is pep440-compliant...\n'
python3 -m pep440 "$VERSION"
VERSION_P="v$VERSION"

printf '\nPerforming last-minute formatting...\n'
black src
isort src
git add . || true
git commit -am "Format code for release $VERSION" || true

printf '\nCreating release branch...\n'
git tag -m "Release $VERSION_P" "$VERSION"
git checkout -b release/"$VERSION_P"

printf '\nBuilding python wheel & source dist...\n'
python3 -m build

#echo '\nBuilding docker image...'
#docker buildx build -t nexy7574/nio-bot:"$VERSION" --platform linux/amd64,linux/arm64 --load .
#echo "\nDocker image built & imported. You should 'docker image push n3xy7574/nio-bot:$VERSION'."

printf '\nFinalising & pushing release...\n'
git push origin "release/$VERSION_P"  # push the release branch
git push origin "$VERSION_P"  # push the tag itself

printf '\nSwitching back to master for further development...\n'
git checkout master

printf '\nOpening browser so that you can upload the wheels to the tag\n'
xdg-open file://"$PWD"/dist &
xdg-open "https://github.com/EEKIM10/niobot/releases/edit/$VERSION" &

printf '\nDone!\n'
