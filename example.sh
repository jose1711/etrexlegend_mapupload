#!/bin/bash
# pull map data from geofabrik around Bratislava (capital of Slovakia),
# convert to Garmin map and send to eTrex Legend via serial connection
#
for i in curl splitter mkgmap
do
  which $i >/dev/null 2>/dev/null || {
    echo "$i missing - please install it and run again"
    exit 1
  }
done
tmpdir=$(mktemp -d)
curdir=$(pwd)
country_url=http://download.geofabrik.de/europe/slovakia-latest.osm.pbf
bbox=17.0974,48.1285,17.202,48.1775

# recommended: use custom style to make map smaller
# cp -r etrex_style "${tmpdir}"
# cp mkgmap.args "${tmpdir}/mkgmap.args"

echo "Using ${tmpdir} for temporary data"
cd "${tmpdir}"

echo "Downloading OSM data.."
curl -s "${country_url}" | osmconvert - -b="${bbox}" -o=map.osm.pbf

echo "Converting to Garmin map.."
splitter map.osm.pbf >splitter.log 2>splitter.err
# mkgmap --gmapsupp -c mkgmap.args 6*osm.pbf >mkgmap.log 2>mkgmap.err
mkgmap --gmapsupp 6*osm.pbf >mkgmap.log 2>mkgmap.err

if [ -f gmapsupp.img ]
then
  echo "Generated gmapsupp.img has $(du -sk gmapsupp.img | awk '{print $1}') kB"
else
  echo "Process of generating gmapsupp.img failed :-("
  echo "Review mkgmap.* and splitter.* files inside ${tmpdir}"
  exit 1
fi
echo "Connect eTrex Legend and hit Return or hit Ctrl-C.."
read
python "${curdir}/etrex_upload.py"
