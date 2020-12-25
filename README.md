# Journey to Day One Importer

> **NOTICE**: I am not affiliated with the companies behind these applications. I created this script for my own use. Use at your own discretion.

A command-line tool to migrate your Journey entries to Day One.

Usage instructions:

1. Export your DayOne journal entries to a .zip file.
2. Extract the .zip file into a directory.
3. From a Terminal window, execute the following from the root of the repository:

```shell
$ python3 j2d.py <name-of-target-journal> <path-to-unzipped-export-directory>
Added: 1536079037061-o0c7k9jp94bdssws -> 08FF91BA31074546847946D066E652AA
Added: 1524500154963-4tjvzwyoaltaoo6i -> 9A7177F4B56541E6AAEF6E3FBDC5BFD9
...

621 succeeded, 0 failed, 4 skipped
```

