#!/bin/bash
for file in *.jpg *.JPG
do 
  magick $file -resize 1024x -quality 75 $file 
done
# gs -sDEVICE=pdfwrite -dCompatibilityLevel=1.4 -dPDFSETTINGS=/ebook -dNOPAUSE -dBATCH -sOutputFile=head_unit_preconditioning_kit_EV6_install.pdf Kia\ EV6\ -\ Harness\ Installation\ Guide.pdf

