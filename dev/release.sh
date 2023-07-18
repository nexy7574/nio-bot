#!/usr/bin/env bash
# PyPi releases are automatically handled by github actions - this script simply builds & uploads a tag.
set -e
printf "Enter the version number: "
read -r VERSION
echo '\nEnsuring version is pep440-compliant...'
python3 -m pep440 "$VERSION"
VERSION_P="v$VERSION"

echo '\nCreating release branch...'
git checkout -b release/"$VERSION_P"

echo '\nPerforming last-minute formatting...'
black src
isort src
git add src || true
git commit -m "Format code for release $VERSION" || true

echo '\nBuilding python wheel & source dist...'
python3 -m build

echo '\nBuilding docker image...'
docker buildx build -t nexy7574/nio-bot:"$VERSION" --platform linux/amd64,linux/arm64 --load .
echo "\nDocker image built & imported. You should 'docker image push n3xy7574/nio-bot:$VERSION'."

echo '\nFinalising & pushing release...'
git tag -m "Release $VERSION" "$VERSION"
#git push --tags origin release/"$VERSION"

echo '\nSwitching back to master for further development...'
git checkout master

echo '\nOpening browser so that you can upload the wheels to the tag'
xdg-open file://"$PWD"/dist &
xdg-open "https://github.com/EEKIM10/niobot/releases/edit/$VERSION" &

echo '\nDone!'
