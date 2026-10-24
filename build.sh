#!/bin/bash
set -e
cd "$(dirname "$0")"

PYTHON=/Library/Frameworks/Python.framework/Versions/3.13/bin/python3

echo "=== Generiere Icon …"
$PYTHON generate_icon.py

echo "=== Baue App …"
$PYTHON -m PyInstaller MonitorQS.spec --noconfirm

echo "=== Erstelle DMG …"
hdiutil create -volname "MonitorQS" \
  -srcfolder "dist/MonitorQS.app" \
  -ov -format UDZO \
  "dist/MonitorQS.dmg"

echo ""
echo "Fertig: dist/MonitorQS.dmg"
