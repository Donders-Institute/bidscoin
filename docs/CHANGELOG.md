# Changelog

All notable changes to this project will be documented in this file. The format is based on [Keep a Changelog](http://keepachangelog.com/en/1.0.0/)

## [3.7.0-dev]

### Added
- A BIDScoin installation test (`bidscoin -t`)
- A bidseditor button to save the Options to a (default) template bidsmap
- Sub-/ses-prefix settings to bidsmap['Options']['bidscoin']

### Changed
- Plugins should now have a `is_sourcefile` and a `get_attribute` function and have a simpler API (-> DataSource class)
- The intricate filtering of the `nrfiles` property by the other filesystem properties has been removed and is now a pure/unfiltered file-system property

## [3.6.2] - 2021-05-31

### Fixed
Removed the redundant importlib dependency from the requirements (could cause an installation error)

## [3.6.1] - 2021-05-20

### Fixed
The bidscoiner no longer sometimes crashes when dcm2niix produces custom suffixes (e.g. for multi-echo data)

## [3.6.0] - 2021-05-13

### Added
- Support for BIDS v1.6.0 (-> PET)
- Separate tabs for DICOM and PAR to edit all the mappings of mixed datasets in a single bidseditor session
- Run-item matching on filesystem properties, i.e. on the pathname, filename and filesize and nr of files in the folder. This can be used in conjunction with the (DICOM/PAR) attributes
- A meta-data dictionary that can be edited with the bidseditor and that will be added to the json sidecar files by the bidscoiner
- More user feedback in the GUI for new BIDS-compliancy checks on missing or invalid bids data
- A right-click menu option to remove a run-item from the bidsmap (advanced usage)
- The option to load a new bidsmap in the bidseditor
- Enable the user to edit json, yaml, tsv and other non-DICOM / non-PAR files with double-clicks in the data browser
- A central 'bidscoin' package function with various utilities, such as listing and installing BIDScoin plugins or executables
- Plugins can have their own 'test' routine that can be called from the bidseditor

### Changed
- Using regular expressions instead of fnmatch to match (template bidsmap) attribute values. This makes the templates more powerful and flexible
- Moved the bidsmapping and bidscoining functionality to stand-alone plugins (changed API), making plugins a first-class BIDScoin citizen
- The plugins have moved to the bidsmap['Options'], where they have their own key-value options dictionary (changed API)
- Move IntendedFor field over to the new meta-data dictionary
- Renamed the `leave_out` datatype to `exclude`
- Re-introduced skipping hidden folders (hidden files are also skipped)
- Moved the 'pulltutorial' function over to the new 'bidscoin' function

### Removed
- P7 and nifti support (it was never implemented anyhow)
- The option to edit new mappings on-the-fly in the bidsmapper (`-i 2`)
    
## [3.5.3] - 2021-04-13

### Fixed
- Save non-standard fieldmaps in the derivative folder
- Add 'AcquisitionTime' to physio json-files and add the physio-files to the *_scans.tsv file 
    
## [3.5.2] - 2021-03-21

### Fixed:
- pypi upload
    
## [3.5.1] - 2021-03-21

### Added
- BIDScoin version update checks

### Fixed
- Speed optimizations
- Code clean-up
- More robust dcm2niix output handling
    
## [3.5] - 2021-03-08

A significant rewrite and evolution of BIDScoin!

### Added
- Support for BIDS v1.5
- Support for Siemens advanced physiological logging data
- Improved GUI help tooltips and user feedback
- Improved feedback and control for invalid bidsnames
- Validation of run-items and bidsmaps against the BIDS schema

### Changed
- Use the dccn template bidsmap as the default

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
- Support for zipped/tarred DICOM directories
    
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

[3.7.0-dev]: https://github.com/Donders-Institute/bidscoin/compare/3.6.1...HEAD
[3.6.2]: https://github.com/Donders-Institute/bidscoin/compare/3.6.1...3.6.2
[3.6.1]: https://github.com/Donders-Institute/bidscoin/compare/3.6.0...3.6.1
[3.6.0]: https://github.com/Donders-Institute/bidscoin/compare/3.5.3...3.6.0
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
