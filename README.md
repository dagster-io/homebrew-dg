# `dg` Homebrew Formula

## Installation

```
brew install dagster-io/tap/dg
```

## Updating resources

```
brew update-python-resources Formula/dg.rb --print-only
```

## Local installation

```
brew reinstall --formula --build-from-source ./Formula/dg.rb
```


## Release process
export DG_RELEASE_VERSION=0.26.16
python build.py create-rc
python build.py push-tag
python build.py create-github-release
