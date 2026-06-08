# Contributing to OtoScope

First off, thank you for considering contributing to OtoScope! It's people like you that make OtoScope such a great tool for the community.

## Where do I go from here?

If you've noticed a bug or have a feature request, make one! It's generally best if you get confirmation of your bug or approval for your feature request this way before starting to code.

## Fork & create a branch

If this is something you think you can fix, then fork OtoScope and create a branch with a descriptive name.

## Get the test suite running

Make sure you're running the tests before you start changing the code! We use `pytest` for the backend.

```bash
cd server
python -m pytest
```

## Implement your fix or feature

At this point, you're ready to make your changes! Feel free to ask for help; everyone is a beginner at first.

## Make a Pull Request

At this point, you should switch back to your master branch and make sure it's up to date with OtoScope's master branch:

```bash
git remote add upstream git@github.com:YOUR_USERNAME/OtoScope.git
git checkout master
git pull upstream master
```

Then update your feature branch from your local copy of master, and push it!

```bash
git checkout 325-add-my-awesome-feature
git rebase master
git push --set-upstream origin 325-add-my-awesome-feature
```

Finally, go to GitHub and make a Pull Request.

Thank you!
