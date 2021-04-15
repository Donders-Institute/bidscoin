# Changelog

All notable changes to this project will be documented in this file. The format is based on [Keep a Changelog](http://keepachangelog.com/en/1.0.0/)

## [Unreleased]

### Added
- Support for BIDS v1.6
- Added separate tabs for DICOM and PAR to edit all the mappings of mixed datasets
- Added matching on the filesystem properties
- Allow the user to edit json, yaml and other non-DICOM or PAR-files in the data browser
- User feedback in the GUI for new BIDS compliancy checks

### Changed
- Using regular expressions instead of fnmatch to match attribute values
- Moved the bidsmapping and bidscoining functionality to plugins (changed API)
- Re-introduced skipping hidden folders (hidden files are also skipped)

### Removed
- P7 / nifti mapping

## [3.5.3] - 2021-04-13

### Fixed
- Save non-standard fieldmaps in the derivative folder
    
## [3.5.2] - 2021-03-21

### Fixed:
- pypi upload
    
## [3.5.1] - 2021-03-21

### Added
- Improved BIDScoin version information

### Fixed
- Speed optimizations
- Code clean-up
- More robust dcm2niix output handling
    
## [3.5] - 2021-03-08

A significant rewrite and evolution of BIDScoin!

### Added
- Support for BIDS 1.5
- Support for Siemens advanced physiological logging data
- Improved GUI help tooltips and user feedback
- Improved feedback and control for invalid bidsnames
- Validation of the template bidsmap against BIDS schema

### Fixed
- Simplified and improved (hopefully) handling of fieldmaps
    
## [3.0.8] - 2020-09-28

### Fixed
- Various minor bugs
    
## [3.0.6] - 2020-08-05

### Fixed
- Minor but important bugfix in the setup :-)
    
## [3.0.5] - 2020-08-05

### Added
- A download tool for tutorial data
- A tool for regenerating the participants.tsv file

### Fixed
- Various bugs
    
## [3.0.4] - 2020-05-14

### Added
* `Export` function in the bidseditor to allow for adding run items to existing (template) bidsmaps
* Support for Unix-shell style wildcards for matching run items in the bidsmap

### Changed
* Improved DCCN example template bidsmap

### Fixed
* Various minor bugs
    
## [3.0.3] - 2020-04-14

### Fixed
- A small bugfix to properly handle appending dcm2niix suffices to the BIDS acq-label
    
## [3.0.2] - 2020-04-06

### Fixed
- Special thanks to [Thom Shaw](https://github.com/thomshaw92), who was patient enough to keep testing untested bugfixes (#56) and helped making BIDScoin better :-)
    
## [3.0.1] - 2020-04-04

### Added
- A 'provenance store' in the `bidsmapper` to fix a bug (#56 ) and allow for moving the bids-folder around
    
## [3.0] - 2020-04-01

A Significant rewrite to make BIDScoin more robust, user friendly and feature-rich :-)

### Added
* First support for Philips PAR / REC data format
* A BIDS compliant defacing tool
* A BIDS compliant multi-echo combination tool
* Much improved documentation (https://bidscoin.readthedocs.io)
    
## [2.3.1] - 2019-09-12

### Fixed
* a small but important bug that caused datasets without fieldmaps to crash (my test datasets all had fieldmaps :-))
    
## [2.3] - 2019-08-29

A lot of improvements have landed in 2.3, making it the best release of the 2-series by far!

### Added
* The possibility to edit Participant labels
* Various tests and checks in Options to ensure creating good working bidsmaps / BIDS output data
* Upgraded compliance with bids v1.2.1
* The possibility to leave-out certain data types / runs

### Changed
* A new workflow that is easier and more consistent
* Greatly improved graphical user interface and error/warning reporting
* Improved bidsmap_dccn template

### Fixed
* Significant code refactoring to squash a number of important bugs and make the code more robust and maintainable
    
## [2.2] - 2019-07-11

### Added
* Options tab to edit and test the bidscoin Options
* A leave-out option (to ignore runs / prevent them from showing up in the BIDS directory)
* A graphical interface to the bidsmapper
* Improved logging
* Improved the DICOM attribute *wildcard* feature

### Changed
* New layout of the main and edit windows

### Fixed
* Various bugfixes
    
## [2.1] - 2019-06-23

### Added
* Editing of bidsmap Options

### Fixed
* `IntendedFor` in fieldmap json sidecar files
* Code redundancy
    
## [2.0] - 2019-06-18

A major release and rewrite with important user-facing improvements

### Added
* A shiny GUI :-)
* A new and much easier workflow

### Fixed
* Various bugfixes
    
## [1.5] - 2019-03-06

### Added
* Support for PET scans
* Support for DICOMDIR data
* Saving of template sidecar files in the bids output directory

### Changed
* increased flexibility for renaming / reorganising the raw (input) data structure
* Added provenance data to the bidsmap/yaml files

### Fixed
* various bugfixes
    
## [1.4] - 2018-10-22

### Added
* Cross platform support
* Installation as a python module
* Improved version control
* Improved BIDS compliance
    
## [1.3] - 2018-09-28

### Changed
* Refactored bidsmap naming

### Fixed
* Various bugs
    
## [1.2] - 2018-09-14

### Added
* Improved fieldmap support

### Changed
* Yaml-syntax

## 1.0 - 2018-07-04

A first stable release of BIDScoin :-)

### Added
* Support the conversion of organised sub/ses DICOM folders to BIDS

### To do
* Add support for non-imaging data

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
