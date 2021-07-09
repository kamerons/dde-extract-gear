# DDE Extract Gear

## Problem
Dungeon Defenders Eternity is a game in which the player must equip a signifcant amount of gear.
The gear you wear accounts for the majority of your stats in the post-game.
Given that the player can have up to 1000 gear items in their inventory at once, how does the player find
which combination of gear is best?
This repository is the start of a solution to this problem. It collects all of the stats of the gear stored
in the players inventory in a JSON format for further analysis.

## What is it
This is a machine learning repository that extracts gear information from the Dungeon Defenders Eternity Game.
The repository contains a number of different tasks used to collect training images from the game, label training images, train a neural network, and use the trained neural network to collect data from the game into JSON.

## How to use it

`main.py` has a number of different subtasks associated with it.
Each task produces data that can be used by the next task until eventually a completely functional classifier is built.

### collect
Collects training data from the game. Images will be taken of the various armor locations on the screen.
You will need to hover over the various armor locations in the game, and press o then p to take a screenshot.
These images will later serve as training data.

### split
Splits the training images into their individual components.  Each training image is a whole game screenshot.
However each screenshot contains multiple gear types and digits for training.

### index
Used to label the training images.  Images will be presented and the user will be given an opportunity to
label the images and correct any mistakes.

### train
Used to train a neural network. The neural network will be training to classify both digits and types of armor.

### evaluate
Used to evaluate the current accuracy of the neural network, and various pixel configurations.
Compares the accuracy of the current configurations to marked training data.

### fast-index
Augment the training data from a card json. The card json has the stats and type of already taken training images.
These card images are then split into their components and labelled using the card json.

## gear
The main program. Images will be taken of the various armor locations on the screen.
You will need to hover over the various armor locations in the game, and press o then p to take a screenshot.
These images will be processed and the stats of the armor will be stored on disk.
