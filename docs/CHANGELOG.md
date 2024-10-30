# Changelog

*All notable changes to this project will be documented in this file. The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/)*

## [dev]

## [4.5.0] - To be determined

### Added
- An events2bids plugin for converting Presentation logfiles to events tsv-files

### Changed
- Drop saving data in the derivatives folder (i.e. this was not required by BIDS after all)
 
## [4.4.0] - 2024-10-02

### Added
- Support for BIDS v1.10.0 (including MRS data)

### Changed
- BIDScoin's main API, which now includes new classes to separate the logic from the bidsmap data and make the code cleaner, better organized and easier to maintain
- Dropped support for Qt5
- Plugins are now installed in BIDScoin's user configuration directory

## [4.3.3] - 2024-07-12

### Added
- A bidseditor context menu for comparing, editing or adding multiple run-items (GitHub issue #239)
- A ``fixmeta`` bidsapp for retrospective metadata editing

### Changed
- Merged the DRMAA `cluster` and `nativespec` input arguments
- DRMAA support for slicereport (instead of calling qsub or sbatch)

## [4.3.2] - 2024-03-29

### Fixed
- A regression was introduced when fixing GitHub issue #229 (now reverted)

## [4.3.1] - 2024-03-27

### Added
- Update B0FieldIdentifier/Source when having multiple fieldmap runs (`GitHub` issue [#198](https://github.com/Donders-Institute/bidscoin/issues/198))
- Slicereport support for all nibabel file-formats
- The `BIDSCOIN_TRACKUSAGE` environment variable for setting trackusage on the fly (see `bidscoin --trackusage show`)

### Changed
- The range specifier for IntendedFor and B0-field tags now includes the final limit, e.g. `<<task:[0:2]>>` includes two runs acquired after the fieldmap instead of one

## [4.3.0] - 2024-02-16

### Added
- Support for BIDS 1.9.0
- A new special `<<session>>` dynamic meta-data value (most notably useful for creating session specific B0FieldIdentifier/Source tags)
- DICOM tags from the Siemens CSA header can now also be used
- The `dir` entity value can now be parsed from the DICOM header using `<PhaseEncodingDirection>` (Siemens and GE)
- The bidsmapper now automatically sets the `part` entity value (e.g. `part-phase`) for non-magnitude images (Siemens)
- A `--cluster` option for running bidscoiner in parallel on a (DRMAA enabled) HPC
- Option to exclude datatypes from being saved in bids/derivatives
- A `bidsmap_bids2bids` template bidsmap for nibabel2bids to edit existing BIDS datasets
- A `bidscoiner.tsv` log-file containing a concise overview of all input to output file conversions
- Integrated fslmaths preprocessing on slicereport input images
- BIDScoin duecredit reports
- A new environment variable `BIDSCOIN_CONFIGDIR=/writable/path/to/configdir` for using alternative configurations

### Changed
- `bidscoiner_plugin()` API: you can (should) return a personals dict (instead of writing it to `participants.tsv`)
- Using DRMAA library for skullstrip (instead of qsub/sbatch)
- Removed the pet2bids and phys2bids plugins (code is no longer actively developed)
- Sorting of DICOMDIR files has changed in some cases to make it more robust
- Retrieving the bidsmap yaml-file from the user argument is less fuzzy

## [4.2.1] - 2023-10-30

### Added
- A bidsmap schema file
- Enhanced DICOM (XA30) support for physiological data (backported from the CMRR repository)
- Slurm support for the `skullstrip` and `slicereport` bidsapps

### Changed
- Use a true list (instead of a semi-colon separated string) for the bidsmap's `bidsignore` field
- The telemetry url

## [4.2.0] - 2023-10-16

### Added
- The option to pip-install dcm2niix as `extras`
- A user config file (github issue #197)
- Optional usage tracking (github issue #200)

### Changed
- The template bidsmaps are now stored in `[home]/.bidscoin/[version]/templates`

## [4.1.1] - 2023-09-14

### Changed
- Bugfixes to support (XA30) enhanced DICOM
- Bugfix to catch multi-echo series with dynamic runindex <<>>
- Prioritize fmap data discovery
- Remove invalid bval/bvec files
- Reduce filesize warnings
- Skip all hidden folders and files
- Tutorial update

## [4.1.0] - 2023-08-29

### Added
- Use SeriesInstanceUID in dicomsort as a fallback
- Update the paths in the provenance store if the bidsfolder was moved
- A template bidsmap entry to support CT (BEP024)
- Manpages (not on Windows)
- A new `<<>>` dynamic run-index (default), that behaves the same as `<<1>>` when multiple runs are acquired, otherwise it is omitted/void (PR #195)

### Changed
- Template bidsmap tweaks to support (XA30) enhanced DICOM
- Skip all subfolders of hidden folders
- GUI upgraded from Qt5 to Qt6 (supporting the new Apple silicon)

## [4.0.0] - 2023-03-18

### Added
- Support for BIDS 1.8.0
- Support for handling of non-alphanumeric characters in sub/ses prefixes
- A new (optional) pet2bids plugin
- A `skullstrip` tool (a bids-wrapper around FreeSurfer/synthstrip)
- A `slicereport` QC tool (a bids-wrapper around FSL/slicesdir)
- A unit/integration test & CI framework
- New Dockerfile and Apptainer/Singularity definition files to run BIDScoin in a container
- A BIDSCOIN_DEBUG environment variable to run bidscoin in a more verbose debug mode
- VERBOSE and SUCCESS logging levels
- Checks using the bids-validator python module
- Options to perform study/template bidsmap tests with `bidscoin -b / -t`
- Option to list and install template bidsmaps
- Many bugfixes, user interface improvements and tweaks

### Changed
- The default behaviour is now to **not** unzip data in the sourcefolders anymore. Instead, users can use the `--unzip` option in the bidsmapper
- The spec2nii plugin is no longer added by default but is optional
- The dcm2niix2bids plugin no longer handles PET data (this is now handled by the pet2bids plugin)
- Removed BIDScoin's redundant/confusing `datatypes` option from the bidsmap
- Removed the obscure `participants` option from bidscoiner
- Major code refactoring

## [3.7.4] - 2022-10-21

### Added
- Added support for the ABCD GE pepolar pulse sequence
- Use an orange bidsname font in the bidseditor for `.bidsignore` datatypes
- A (right-click) context menu in the bidseditor to import meta-data from disk into the meta-table
 
### Changed
- Remove the DCCN specific dcm2niix module usage in the bidsmap template
- Add `-l n` to the dcm2niix arguments to revert old UINT16 -> INT16 behaviour (otherwise fmriprep outputs are twice as large)
- No longer enforce BIDS compliance on `.bidsignore` datatypes

### Fixed
- Sorting flat DICOM data (in a temporary working directory)
- The dcm2niix module (if not removed) raised an error that prevented handling dcm2niix suffixes

## [3.7.3] - 2022-07-13

### Added
- The usage of json sidecar files as a datasource for attribute values
- A template bidsmap for the [ScanSessionTool](https://github.com/fladd/ScanSessionTool)

### Changed
- Dicomsort now searches recursively over the sessionfolder
- The dcm2niix2bids plugin now searches recursively for DICOM Series folders
- Images that have already been defaced are now skipped
- Prepend the rawfolder name & subprefix for more robust subject-/session-label filepath extraction

### Fixed
- Pydeface not parsing subject/session labels from the filepath
- The non-HPC use of pydeface no longer requires DRMAA installation
- Account for `*` and `?` wildcards in the sub/ses prefixes in the bidsmapper
- Account for dynamic values with non-matching regular expressions (special thanks to Mateusz Pawlik)
- Various minor bugs

## [3.7.2] - 2022-03-13

### Fixed
- The installation of the BIDS schema files

## [3.7.1] - 2022-03-11

### Added
- IntendedFor can now be appended with a "bounding" term to deal with duplicated field maps from interrupted sessions
- The possibility to process subject folders without prefix
- Support for BIDS 1.7 (e.g. for the new `B0FieldSource` and `B0FieldIdentifier` field-map meta fields)
- A `nibabel2bids` plugin (e.g. to convert NIfTI datasets to BIDS)
- Plugin `meta` option setting to enrich json sidecar files or add data that is not supported

### Changed
- Removed/changed redundant subject/session prefix input arguments (now stored in the bidsmap)
- The `IntendedFor` search feature now works independent of plugins

### Fixed
- The bidscoin installation test in the bidseditor
- The IntendedFor list when combining echos

## [3.7.0] - 2021-12-20

### Added
- A BIDScoin installation test (`bidscoin -t`)
- Option to install extra packages, such as phys2bids
- A bidseditor button to save the Options to a (default) template bidsmap
- Sub-/ses-prefix settings and BIDS/extra_data/excluded datatypes in `bidsmap['Options']['bidscoin']`
- Regular expressions for extracting property and attribute substrings from dynamic values via a <\<key:regular_expression>> syntax
- A plugin for spec2nii to convert MR spectroscopy data
- An experimental plugin for phys2bids to convert physiological data
- An experimental plugin for pet2bids to convert MR spectroscopy data
- Added a multi-echo deface function `medeface` that uses the same defacemask for all echo-images
- The possibility to extract DICOM values using pydicom-style tag numbers (in addition to the attribute name)
- The possibility for plugins to set default bidsmappings and Options when installed
- A Singularity container configuration file
- Improved (more fine-grained) plugin installation procedures
- The option to remove decimals from age and discard acquisition dates from the metadata

### Changed
- Plugins should now have a `has_support` and a `get_attribute` function and have a simpler/changed API (-> DataSource class)
- The intricate filtering of the `nrfiles` property by the other filesystem properties has been removed and is now a pure/unfiltered file-system property
- The default `<<SourceFilePath>>` keyword has been replaced by the more flexible <\<filepath:/sub-(.*?)/>> property to extract the subject/session label
- The dcm2bidsmap and the dcm2niix2bids plugins have been merged
- The dicomsort utility has new naming-scheme functionality
- Removed the obsolete bidsmap_template.yaml file

### Fixed
- Avoid storing Python literal structures as strings

## [3.6.3] - 2021-06-14

### Fixed
Remove regular expression metacharacters from the source attribute if needed (could cause a regex compile error)
Fixed for list of dynamic <<Intendended><For>> fields

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
- Enable the user to edit json, yaml, tsv and other non-DICOM/non-PAR files with double-clicks in the data browser
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
- P7 and NIfTI support (it was never implemented anyhow)
- The option to edit new mappings on-the-fly in the bidsmapper (`-i 2`)
    
## [3.5.3] - 2021-04-13

### Fixed
- Save non-standard field maps in the derivative folder
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
- Use the DCCN template bidsmap as the default

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
- `Export` function in the bidseditor to allow for adding run items to existing (template) bidsmaps
- Support for Unix-shell style wildcards for matching run items in the bidsmap

### Changed
- Improved DCCN example template bidsmap

### Fixed
- Various minor bugs
    
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

A Significant rewrite to make BIDScoin more robust, user-friendly and feature-rich :-)

### Added
- First support for Philips PAR/REC data format
- A BIDS compliant defacing tool
- A BIDS compliant multi-echo combination tool
- Much improved documentation (https://bidscoin.readthedocs.io)
    
## [2.3.1] - 2019-09-12

### Fixed
- a small but important bug that caused datasets without field maps to crash (my test datasets all had field maps :-))
    
## [2.3] - 2019-08-29

A lot of improvements have landed in 2.3, making it the best release of the 2-series by far!

### Added
- The possibility to edit Participant labels
- Various tests and checks in Options to ensure creating good working bidsmaps / BIDS output data
- Upgraded compliance with bids v1.2.1
- The possibility to leave-out certain data types/runs

### Changed
- A new workflow that is easier and more consistent
- Greatly improved graphical user interface and error/warning reporting
- Improved bidsmap_dccn template

### Fixed
- Significant code refactoring to squash a number of important bugs and make the code more robust and maintainable
    
## [2.2] - 2019-07-11

### Added
- Options tab to edit and test the bidscoin Options
- A leave-out option (to ignore runs / prevent them from showing up in the BIDS directory)
- A graphical interface to the bidsmapper
- Improved logging
- Improved the DICOM attribute *wildcard* feature

### Changed
- New layout of the main and edit windows

### Fixed
- Various bugfixes
    
## [2.1] - 2019-06-23

### Added
- Editing of bidsmap Options

### Fixed
- `IntendedFor` in field map json sidecar files
- Code redundancy
    
## [2.0] - 2019-06-18

A major release and rewrite with important user-facing improvements

### Added
- A shiny GUI :-)
- A new and much easier workflow

### Fixed
- Various bugfixes
    
## [1.5] - 2019-03-06

### Added
- Support for PET scans
- Support for DICOMDIR data
- Saving of template sidecar files in the bids output directory

### Changed
- increased flexibility for renaming/reorganizing the raw (input) data structure
- Added provenance data to the bidsmap/yaml files

### Fixed
- various bugfixes
    
## [1.4] - 2018-10-22

### Added
- Cross-platform support
- Installation as a Python module
- Improved version control
- Improved BIDS compliance
    
## [1.3] - 2018-09-28

### Changed
- Refactored bidsmap naming

### Fixed
- Various bugs
    
## [1.2] - 2018-09-14

### Added
- Improved field map support

### Changed
- YAML-syntax

## 1.0 - 2018-07-04

A first stable release of BIDScoin :-)

### Added
- Support the conversion of organized sub/ses DICOM folders to BIDS

### To do
- Add support for non-imaging data

[dev]: https://github.com/Donders-Institute/bidscoin/compare/4.4.0...HEAD
[4.3.4]: https://github.com/Donders-Institute/bidscoin/compare/4.3.3...4.4.0
[4.3.3]: https://github.com/Donders-Institute/bidscoin/compare/4.3.2...4.3.3
[4.3.2]: https://github.com/Donders-Institute/bidscoin/compare/4.3.1...4.3.2
[4.3.1]: https://github.com/Donders-Institute/bidscoin/compare/4.3.0...4.3.1
[4.3.0]: https://github.com/Donders-Institute/bidscoin/compare/4.2.1...4.3.0
[4.2.1]: https://github.com/Donders-Institute/bidscoin/compare/4.2.0...4.2.1
[4.2.0]: https://github.com/Donders-Institute/bidscoin/compare/4.1.1...4.2.0
[4.1.1]: https://github.com/Donders-Institute/bidscoin/compare/4.1.0...4.1.1
[4.1.0]: https://github.com/Donders-Institute/bidscoin/compare/4.0.0...4.1.0
[4.0.0]: https://github.com/Donders-Institute/bidscoin/compare/3.7.4...4.0.0
[3.7.4]: https://github.com/Donders-Institute/bidscoin/compare/3.7.3...3.7.4
[3.7.3]: https://github.com/Donders-Institute/bidscoin/compare/3.7.2...3.7.3
[3.7.2]: https://github.com/Donders-Institute/bidscoin/compare/3.7.1...3.7.2
[3.7.1]: https://github.com/Donders-Institute/bidscoin/compare/3.7.0...3.7.1
[3.7.0]: https://github.com/Donders-Institute/bidscoin/compare/3.6.3...3.7.0
[3.6.3]: https://github.com/Donders-Institute/bidscoin/compare/3.6.2...3.6.3
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
