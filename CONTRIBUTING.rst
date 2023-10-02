========================
Contributing to BIDScoin
========================

Project organization
--------------------

* `bidscoin/ <./bidscoin>`__ is the main Python module where major development is happening, with main submodules being:

  - ``bidsapps/`` - Applications that can process BIDS or BIDS-like data folders
  - ``cli/`` - wrappers and argument parsers bringing the BIDScoin functionality to the command line
  - ``heuristics/`` - Pre-installed template bidsmaps
  - ``plugins/`` - Pre-installed plugins
  - ``schema/`` - Schema files from the `BIDS specifications <https://github.com/bids-standard/bids-specification/tree/master/src/schema>`__
  - ``utilities/`` -

* `docs/ <./docs>`_ - The Sphynx documentation directory
* `tests/ <./tests>`_ - helper utilities used during development, testing, and distribution of

How to contribute
-----------------

The preferred way to contribute to the BIDScoin code base is
to fork the `main repository <https://github.com/nipy/bidscoin/>`_ on GitHub.

If you are unsure what that means, here is a set-up workflow you may wish to follow:

0. Fork the `project repository <https://github.com/nipy/bidscoin>`_ on GitHub, by clicking on the “Fork” button near the top of the page — this will create a copy of the repository writeable by your GitHub user.
1. Set up a clone of the repository on your local machine and connect it to both the “official”
   and your copy of the repository on GitHub::

     git clone git://github.com/nipy/bidscoin
     cd bidscoin
     git remote rename origin official
     git remote add origin git://github.com/YOUR_GITHUB_USERNAME/bidscoin

2. When you wish to start a new contribution, create a new branch::

     git checkout -b topic_of_your_contribution

3. When you are done making the changes you wish to contribute, record them in Git::

     git add the/paths/to/files/you/modified can/be/more/than/one
     git commit

3. Push the changes to your copy of the code on GitHub, following which Git will provide you with a link which you can click to initiate a pull request::

     git push -u origin topic_of_your_contribution

(If any of the above seems overwhelming, you can look up the `Git documentation <http://git-scm.com/documentation>`__ on the web.)


Coding guidelines
-----------------

It is recommended to check that your contribution complies with the following rules before submitting a pull request:

* All cli functions (i.e. functions that have an entrypoint + manpage in ``pyproject.toml``) should have informative docstrings with usage examples presented as argparse epilogues.
* Docstrings are formatted in
* Screens are wide nowadays, so the PEP directives for short code lines do not need to be respected
* Because line length is not limited, multi-line readability is preferred, e.g. the vertical alignment of ``=`` operators (padded with whitespaces)
* All tests in ``tests`` must pass
* New code should be accompanied by new tests.
