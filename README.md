# Journey to Day One Importer

> **NOTICE**: I am not affiliated with the companies behind these applications. I created this script for my own use. Use at your own discretion.

A command-line tool to migrate your Journey entries to Day One.

## Features:

* Includes attachments: photos, video, and audio 
* Includes tags
* Includes geographic coordinates
* Includes timestamp (timezone aware)
* Imported text looks as expected (no formatting/encoding issues)

## Quickstart:

### Prerequisites

**0. Export your Journey data**

First, download your journal entries and attachments from Journey as a .zip.

Open the Journey app and select _Journey > Preferences > Data > Export/Backup_. We'll assume you want ALL your Journey 
entries and full-quality photo attachment. To do this, adjust the *Start Date* to before the date of your first 
Journey entry and select *Download High Quality Photos*. 

TODO image

Extract the .zip and take note of the file path. You'll need it later to run import your entries into Day One.

```shell
~/Desktop/journey-multiple-1659503382727.zip # <= The original .zip
~/Desktop/journey-multiple-1659503382727     # <= The extracted data we'll need later
```

**1. Install Day One command-line tool**

Next, install the Day One's command-line tool, `dayone2`.

Open the Day One app on your computer. Then, select _Day One > Install Command Line Tools..._

TODO image

Now confirm the installation. Go to your command-line and enter `dayone2`. You should see the usage/help instructions 
(like below). If this doesn't work, you'll likely need to add `dayone2` to your `PATH`.

```shell
$ dayone2
Usage: dayone2 [options] command

 Commands:
   new [text] [text]...
     Creates new entry with optional text. Every text argument will be separated by
     a single space when placed into the new entry. If no text arguments are provided
     then standard input is used by default for the entry text. Use --no-stdin to override
     this behavior.
   
   help
     Display help.
   ...
```

**2. Install this JourneyToDayOne tool (`j2d`)**

Clone this repository and install this JourneyToDayOne package. (Alternatively, if you don't have `git` set up, you can 
simply download the files from GitHub.) Then, use `pip` <u>or</u> `poetry` to install the package.

_Option 1: Installing with pip_

```shell
git clone https://github.com/camflint/JourneyToDayOneImporter.git
cd JourneyToDayOneImporter
pip install -r requirements.txt
```

_Option 2: Installing with `poetry`_

```shell
git clone https://github.com/camflint/JourneyToDayOneImporter.git
cd JourneyToDayOneImporter
poetry install
```

**3. Finally: Import your Journey entries to Day One**

The `j2d` command-line interface needs two things from you to run:

1. `<journey-export-path>` – The path to your exported Journey entries from step 0 above.
2. `<target-day-one-journal-name>` – The name of the Day One journal the tool will write your Journey entries to.

```shell
$ python3 -m src/j2d <target-day-one-journal-name> <journey-export-path>
```

> **Consider doing a test run by creating a new Day One Journal**<br>
> Please realize Day One supports you having more than one journal, with each journal being a separate collection of entries. We assume most users will want to merge their Journey entries into a Day One journal that contains other Day One entries. If this is the case, consider creating a new Day One journal and importing Journey entries into it. It can be hard to undo the import once it's. Performing a test run allows you to confirm everything is working like you want before combining your Journey and Day One entries into one Day One journal.

Example command:

```shell
$ python3 -m src/j2d Journal ~/Desktop/journey-multiple-1659503382727
```

Example output:

```shell
INFO :: [1/548] Entry added to Day One 1642607366221-r34ci988jlbfcj9p -> 6AE834D1EEAC4D1EB60F1B7FCB5482D4: 51 words
INFO :: [2/548] Entry added to Day One 1618073777562-x0izgj4ycrhnawva -> 913E4E86B1FF4026850201865B65E634: 33 words, 1 attachments
INFO :: [3/548] Entry added to Day One 1600811930363-3fecb9edb98b04d3 -> 27A443DA47B14AA686F6FEF3EC256DE9: 9 words
INFO :: [4/548] Entry added to Day One 1636108080475-ygjuqdakvnsq7v7s -> 8E951543083245BEBE382FE2A5949CC5: 106 words
INFO :: [5/548] Entry added to Day One 1632749250036-zy09e0ouylx8umay -> 7E766851E9FA4C6794CFD57A9904B1F4: 70 words, 2 attachments
INFO :: [6/548] Entry added to Day One 1649455338455-nshz5uguxsll5ddp -> 48DD201B58E44900826849CE5D0883A7: 75 words, 1 attachments
INFO :: [7/548] Entry added to Day One 1599606605061-c4e69uyrzf2vlkfm -> FE2E9CE1070C49C186DAF504A96E5BA5: 103 words
INFO :: [8/548] Entry added to Day One 1588519498122-3fa37a50e4b4e390 -> 8CA2F6FFCEE845FF88657840A9038E12: 24 words
INFO :: [9/548] Entry added to Day One 1587922671593-3fd7032669ac7900 -> 3361393677D143939DD75D0D1F7F2200: 8 words
INFO :: [10/548] Entry added to Day One 1655955514760-7j586ikqxh1lwocd -> 5B97E9327371418FA1D02BEBDEF9B0C8: 15 words, 3 attachments
...
INFO :: 547 succeeded, 0 failed, 1 skipped
```
## 4. Follow up: Fix any imperfect entries

Notice the tool reports any entries that had missing attachments, failed, or were skipped. Follow the guidance below to 
recover any missing attachments and address any skipped or failed entries to ensure all your Journey entries and 
attachments are migrated to Day One.

**Locate the log / report**

The first step is to locate the log, which provides a record of any issues we'll now fix.

TODO: improve the report.

**Missing attachments**

Journey's export is not perfect. It appears that sometimes attachments, like photos, are not included in the export.
This results in entries missing a photo for example. But it can also result in an entry being skipped, like when the
Journey entry was just a photo (no text), resulting in nothing left for `j2d` to import into Day One. 

To fix this, you can identify all missing attachments by TODO: explain how to use log/report to identify missing 
attachments and how to individually download and fix them.

**Other issues**

TODO: Provide guidance on other skipped/error issues.
