# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](http://keepachangelog.com/en/1.0.0/)
and this project adheres to [Semantic Versioning](http://semver.org/spec/v2.0.0.html).

## [Unreleased]

    
## [3.5.3] - 2021-04-13

Fix for saving non-standard fieldmaps in the derivative folder
    
## [3.5.2] - 2021-03-21

- Speed optimizations
- Code clean-up
- More robust dcm2niix output handling
- Improved BIDScoin version information


    
## [3.5.1] - 2021-03-21

- Speed optimizations
- Code clean-up
- More robust dcm2niix output handling
- Improved BIDScoin version information
    
## [3.5] - 2021-03-08

Major new features
- Support for BIDS 1.5
- Support for Siemens advanced physiological logging data
- Improved GUI help tooltips and user feedback
- Improved feedback and control for invalid bidsnames
- Simplified and improved (hopefully) handling of fieldmaps
- Validation of the template bidsmap against BIDS schema
    
## [3.0.8] - 2020-09-28

Small bugfixes
    
## [3.0.6] - 2020-08-05

Minor but important bugfix in the setup :-)
    
## [3.0.5] - 2020-08-05

* Added a download tool for tutorial data
* Added a tool for regenerating the participants.tsv file
* Bugfixes


    
## [3.0.4] - 2020-05-14

## Changes:
* Added support for more powerful Unix-shell style wildcards for matching run items in the bidsmap
* Improved DCCN example template bidsmap
* Added an `Export` function in the bidseditor to allow for adding run items to existing (template) bidsmaps
* Bugfixes
    
## [3.0.3] - 2020-04-14

A small bugfix to properly handle appending dcm2niix suffices to the BIDS acq-label
    
## [3.0.2] - 2020-04-06

Special thanks to [Thom Shaw](https://github.com/thomshaw92), who was patient enough to keep testing untested bugfixes (#56) and helped making BIDScoin better :-)
    
## [3.0.1] - 2020-04-04

The introduction of a 'provenance store' in the `bidsmapper` to fix a bug (#56 ) and allow for moving the bids-folder around
    
## [3.0] - 2020-04-01

A major update with significant rewrites to make BIDScoin more robust, user friendly and feature-rich. The main highlights are:
* First support for Philips PAR / REC data format
* A new BIDS compliant defacing tool
* A new BIDS compliant multi-echo combination tool
* Much improved documentation (https://bidscoin.readthedocs.io)

    
## [2.3.1] - 2019-09-12

Fixed a small but important bug that caused datasets without fieldmaps to crash (my test datasets all had fieldmaps :-))
    
## [2.3] - 2019-08-29

A lot of improvements have landed in 2.3, making it the best release of the 2-series by far!
* A new workflow that is easier and more consistent
* Greatly improved graphical user interface and error/warning reporting
* Significant code refactoring to squash a number of important bugs and make the code more robust and maintainable
* Added the possibility to edit Participant labels
* Added various tests and checks in Options to ensure creating good working bidsmaps / BIDS output data
* Upgraded compliance with bids v1.2.1
* Added the possibility to leave-out certain data types / runs
* Improved bidsmap_dccn template
    
## [2.2] - 2019-07-11

Main changes:
* New Options tab to edit and test the bidscoin Options
* New layout of the main and edit windows
* Added a leave-out option (to ignore runs / prevent them from showing up in the BIDS directory)
* Added a graphical interface to the bidsmapper
* Improved the DICOM attribute *wildcard* feature
* Improved logging
* Various bugfixes

    
## [2.1] - 2019-06-23

Added editing of bidsmap Options
Bugfix for IntendedFor in fieldmap json sidecar files
Less code redundancy
    
## [2.0] - 2019-06-18

A new and much easier workflow with a shiny GUI
Many bugfixes and improvements
    
## [1.5] - 2019-03-06

Main changes
* increased flexibility for renaming / reorganising the raw (input) data structure
* various bugfixes
* added support for PET scans
* added support for DICOMDIR data
* added provenance data to the bidsmap/yaml files
* added template sidecar files

    
## [1.4] - 2018-10-22

* Cross platform support
* Installation as a python module
* Improved version control
* Bugfixes and improved BIDS compliance
    
## [1.3] - 2018-09-28

Refactored bidsmap naming and bugfixes
    
## [1.2] - 2018-09-14

Slightly changed yaml-syntax and improved fieldmap support

## 1.0 - 2018-07-04

Supports the conversion of organised sub/ses DICOM folders to BIDS. Does not support non-imaging data yet

[Unreleased]: https://github.com/Donders-Institute/bidscoin/compare/3.5.3...HEAD
[3.5.3]: https://github.com/Donders-Institute/bidscoin/compare/3.5.2...3.5.3
[3.5.2]: https://github.com/Donders-Institute/bidscoin/compare/3.5.1...3.5.2
[3.5.1]: https://github.com/Donders-Institute/bidscoin/compare/3.5...3.5.1
[3.5]: https://github.com/Donders-Institute/bidscoin/compare/3.0.8...3.5
[3.0.8]: https://github.com/Donders-Institute/bidscoin/compare/3.0.6...3.0.8
[3.0.6]: https://github.com/Donders-Institute/bidscoin/compare/3.0.5...3.0.6
[3.0.5]: https://github.com/Donders-Institute/bidscoin/compare/3.0.4...3.0.5
[3.0.4]: https://github.com/Donders-Institute/bidscoin/compare/3.0.3...3.0.4
[3.0.3]: https://github.com/Donders-Institute/bidscoin/compare/3.0.2...3.0.3
[3.0.2]: https://github.com/Donders-Institute/bidscoin/compare/3.0.1...3.0.2
[3.0.1]: https://github.com/Donders-Institute/bidscoin/compare/3.0...3.0.1
[3.0]: https://github.com/Donders-Institute/bidscoin/compare/2.3.1...3.0
[2.3.1]: https://github.com/Donders-Institute/bidscoin/compare/2.3...2.3.1
[2.3]: https://github.com/Donders-Institute/bidscoin/compare/2.2...2.3
[2.2]: https://github.com/Donders-Institute/bidscoin/compare/2.1...2.2
[2.1]: https://github.com/Donders-Institute/bidscoin/compare/2.0...2.1
[2.0]: https://github.com/Donders-Institute/bidscoin/compare/1.5...2.0
[1.5]: https://github.com/Donders-Institute/bidscoin/compare/1.4...1.5
[1.4]: https://github.com/Donders-Institute/bidscoin/compare/1.3...1.4
[1.3]: https://github.com/Donders-Institute/bidscoin/compare/1.2...1.3
[1.2]: https://github.com/Donders-Institute/bidscoin/compare/1.0...1.2
