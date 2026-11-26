#!/bin/sh
# Renders the assembly step pictures in img/ from assembly_steps.scad.
set -e
cd "$(dirname "$0")"
r() {
    openscad -D "view=\"$1\"" -o "img/assembly-$1.png" --imgsize=1200,800 --colorscheme=Tomorrow \
        --camera="$2" assembly_steps.scad
}
r frame 140,70,20,70,0,15,950
r corner -21.7,70.5,55,80,0,25,200
r cap 140,70,20,70,0,15,950
r jaw 5,70.5,0,75,0,20,220
r tensioner -45,70.5,30,75,0,-35,260
r done 140,70,20,65,0,20,950
r clip 301.7,70.5,95,60,0,-30,210
r leads 215,70.5,80,55,0,-25,420
