# etrex_upload.py

Upload Garmin map (gmapsupp.img) to Garmin eTrex Legend via serial
connection.

The motivation was when QLandkarteGT development stopped and its
successor (Qmapshack) removed map upload feature.

Note that eTrex Legend has only 8 MB available memory for custom
maps. Throw aways details that you don't need. Also note that average
upload speed is 8.7 kB/s hence it can take more than 15 minutes to
finish the upload.

## BIG BOLD WARNING

By interacting with eTrex Legend (and maybe other Garmin devices
too) via serial connection in an unexpected way it is possible
to brick your device. This is based on a personal experience.
Although I did manage to unbrick it you may not be that lucky
hence:
  - use at your own risk and do not complain if your Garmin
    can no longer boot
  - backup your data first
  - be prepared for a hw upgrade

Heavily based on code from:
  - qlandkartegt/garmindev (https://sourceforge.net/projects/qlandkartegt/)
  - pygarmin (https://github.com/quentinsf/pygarmin)

Big thanks to authors of both (and related) projects.

## Invocation
Run `etrex_upload.py -h` to get available command-line options.

For a more complete session see `example.sh`. Please note that the script
requires prior installation of `osmconvert`, `mkgmap` and `splitter`.

You can watch a recorded session at https://asciinema.org/a/YsXvwqaeRfgLFkcHZAQYusbYW.
