#!/bin/sh
# Renders the colour pictures in img/: the rig on the desk (frame_assembly.scad) and the
# speaker on the mic (speaker_assembly.scad). Keep these camera settings, so new renders
# match the old ones. --camera is the gimbal form: centre x,y,z, rotation x,y,z, distance.
set -e
cd "$(dirname "$0")"
r() {
    openscad -o "img/$1.png" --imgsize=1600,1000 --colorscheme=Tomorrow --camera="$3" "$2"
}
r rig-colours-front frame_assembly.scad 140,100,5,55,0,-25,800
r rig-colours-back frame_assembly.scad 140,100,5,55,0,155,800
r speaker-front speaker_assembly.scad 0,0,15,80,0,-35,600
r speaker-back speaker_assembly.scad 0,0,15,105,0,150,600
