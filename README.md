# NBot

Discord bot with miscellaneous utilities for communities I like

## Name color
- `/namecolor <hex code>` - Change your name color.

## Emoter
Replaces shorthand words prefixed with `$` with their corresponding [FrankerFaceZ](https://www.frankerfacez.com/emoticons/) and [BetterTV](https://betterttv.com/emotes/top) emotes.

![image](https://user-images.githubusercontent.com/11559683/133935108-4cca1591-4644-4a81-9ba2-d82cd9eea140.png) 

![image](https://user-images.githubusercontent.com/11559683/133935114-e8a6616f-1689-4e26-b0bc-a81428772590.png)

- `/emoter`
  - `add <name> <image url>` - Add a custom emote to the database  
  - `remove <name>` - Remove a custom emote from the database
 
- `/emote`
  - Post a random emote from the database 

Example usage: `hello world $peepoHappy` 

Output: `hello world <:peepoHappy:723458485395914753>`

## PatchBot AdBlocker
Removes sponsored embeds from [PatchBot](https://patchbot.io)

## Chat Message Logger
Periodically log chat messages

## Impersonator 
- `.be <username/nickname>` - Generated fake messages for any user by using Markov chain randomization

## Paraphraser

- `$$ <sentence>` - Paraphrase the input sentence using Natural Language Toolkit (NLTK)

## Weather

- `.setlocation <location>` - Check the weather for a city, state, country, etc. (powered by ClimaCell)
- `/weather` - Tells the weather at saved location
  - `<location>` - (Optional) Override saved location  

### Starboard
Pin messages in a starboard channel by reacting to them with "⭐"

### Translate
Translate input text with automatic language detection

Usage: `.trans <message>`

### Yeller
Yells back at you when you send messages typed completely in capital letters

Example usage: `SOME ALLCAPS MESSAGE`
Example output: `SOME PREVIOUSLY STORED ALLCAPS MESSAGE!!!`

### Cleaner
Periodically remove messages from channels (see config file)
