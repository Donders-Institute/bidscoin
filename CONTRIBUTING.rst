========================
Contributing to BIDScoin
========================

Project organization
--------------------

* `bidscoin/ <./bidscoin>`__ - The main module with the core libraries and applications, as well as some submodules:

  - ``bidsapps/`` - A package of applications that can process BIDS or BIDS-like data folders
  - ``cli/`` - Argument parsers for generating BIDScoin manpages and Command Line Interfaces (CLI)
  - ``heuristics/`` - Pre-installed template bidsmaps
  - ``plugins/`` - Pre-installed plugins
  - ``schema/`` - Schema files from the `BIDS specifications <https://github.com/bids-standard/bids-specification/tree/master/src/schema>`__
  - ``utilities/`` - A package of useful helper tools

* `docs/ <./docs>`_ - The Sphinx `RTD <https://bidscoin.readthedocs.io>`__ documentation repository
* `tests/ <./tests>`_ - The collection of (py)test modules for the `CI development <https://github.com/features/actions>`__ of BIDScoin

How to contribute code
----------------------

The preferred way to contribute to the BIDScoin code base or documentation is to use a `forking workflow <https://www.atlassian.com/git/tutorials/comparing-workflows/forking-workflow>`__, i.e. fork the `main repository <https://github.com/Donders-Institute/bidscoin>`__, create a feature branch, and submit a pull request. If you are unsure what that means, here is a set-up workflow you may wish to follow:

0. Fork the `project repository <https://github.com/Donders-Institute/bidscoin>`_ on GitHub, by clicking on the “Fork” button near the top of the page — this will create a personal copy of the repository.

1. Set up a clone of the repository on your local machine and connect it to both the “official” and your copy of the repository on GitHub::

    git clone https://github.com/Donders-Institute/bidscoin.git
    cd bidscoin
    git remote rename origin official
    git remote add origin git://github.com/[YOUR_GITHUB_USERNAME]/bidscoin

2. Set up a virtual environment and install BIDScoin's dependencies::

    python -m venv venv         # Or use any other tool (such as conda)
    source venv/bin/activate    # On Linux, see the documentation for other operating systems
    pip install -e .[dev]
    # NB: Install dcm2niix yourself (see the online installation instructions)

3. When you wish to start working on your contribution, create a new branch::

    git checkout -b [topic_of_your_contribution]

4. When you are done with coding, you should then test, commit and push your work to GitHub::

    tox                                                  # Run this command from the bidscoin directory (make sure the venv is activated)
    git commit -am "A SHORT DESCRIPTION OF THE CHANGES"  # Run this command every time you have made a set of changes that belong together
    git push -u origin topic_of_your_contribution        # Run this command when you are done and the tox tests are passing

Git will provide you with a link which you can click to initiate a pull request (if any of the above seems overwhelming, you can look up the `Git <http://git-scm.com/documentation>`__ or `GitHub <https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/proposing-changes-to-your-work-with-pull-requests/creating-a-pull-request>`__ documentation on the web)

.. Some Mac users on have encountered issues when running pip install bidscoin[dev] or pip install .[all] during setup. If you encounter this try switching from zsh to bash.

Coding guidelines
-----------------

Please check that your contribution complies with the following rules before submitting a pull request:

* CLI applications (i.e. Python modules that have an entrypoint + manpage in `pyproject.toml <./pyproject.toml>`__) should have informative docstrings and arguments, with usage examples presented as argparse epilogues. All CLIs and plugins must be described in the Sphinx RTD documentation
* Docstrings should be formatted in `Sphinx style <https://sphinx-rtd-tutorial.readthedocs.io/en/latest/docstrings.html>`__
* New modules, classes or functionality should be accompanied with `type hints <https://docs.python.org/3/library/typing.html>`__ and new (py)tests
* All tests performed with `tox <https://tox.wiki>`__ must pass (python environments may be skipped, if at least one of them is tested)
* Screens are wide nowadays, so the PEP directives for short code lines is considered outdated and does not have to be respected. Otherwise use PEP coding styles
* To improve code readability, minor comments can (should) be appended at the end of the code lines they apply to (even if that means right scrolling)
* Horizontal space is not limited, so multi-line readability is preferred, e.g. the vertical alignment of ``=`` operators (i.e. padded horizontally with whitespaces)
* Vertical space should not be readily wasted to promote better overviews and minimize the need for vertical scrolling
