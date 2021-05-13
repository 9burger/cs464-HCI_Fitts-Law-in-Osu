import os, math
import csv
from osrparse import parse_replay_file

# replayLocation = r'C:\\Users\\"Maxwell Nieberger"\\Downloads\\"Raijin no Hidariude - Sound Horizon - top50"\\'
replayLocation = "./replayFiles"
beatmapLocation = "./beatmaps"
beatmapFile = "Sound Horizon - Raijin no Hidariude (AngelHoney) [Alazy].osu"

# hit window 50 : ±-10*(OD-19.95)/Speed
OD = 7
timingWindow = -10 * (OD - 19.95)
circleRadius = 32
BPM = 172
beatLength = 348.837209302326

# csv fields for output
fields = ['time', 'location', 'previous time', 'previous location', 'distance', 'period', 'hit time', 'hit location', 'accuracy error', 'timing error']

def getFiles():
    global replayLocation
    replays = [replayLocation + '/' + x for x in os.listdir(replayLocation)]
    # print(replays)
    return replays

def calcDifficulty(data, CS, OD,):
    # calculate timing window in ms and circle radius
    global timingWindow, circleRadius, beatLength
    
    speed = 1
    if (data.mod_combination >> 4) & 1 == 1:
        # Hard Rock
        print("HR", end=' ')
        OD *= 1.4
        CS *= 1.3
        if CS > 10: CS = 10
    elif (data.mod_combination >> 6) & 1 == 1:
        # DoubleTime
        print("DT", end=' ')
        speed = 1.5
    elif (data.mod_combination >> 8) & 1 == 1:
        # HalfTime
        print("HT", end=' ')
        speed = 0.75
    
    # Timing Windows according to https://www.reddit.com/r/osugame/comments/781ot4/od_in_milliseconds/
    # 300 : ±-6*(OD-13.25)/Speed
    # 100 : ±-8*(OD-17.4375)/Speed
    # 50 : ±-10*(OD-19.95)/Speed
    # use 50 as the largest window that counts as a hit

    timingWindow = -10 * (OD - 19.95) / speed
    circleRadius = 54.4 - (4.48 * CS)
    beatTime = beatLength / speed

    print("50: " + str(timingWindow) + "  Radius: " + str(circleRadius))
    return timingWindow, circleRadius, beatTime

def parseBeatmap(beatmap, beatTime):
    targets = []
    hitObjects = False
    for line in beatmap.readlines():
        if not hitObjects and "[HitObjects]" in line:
            hitObjects = True
        elif hitObjects:
            # line defines a target, format given by osu!
            # x,y,time,type,hitSound,objectParams,hitSample
            targetRaw = line.split(',')

            # reformat target into:
            # target = [time, (x,y), include_in_accuracy_calc]
            if int(targetRaw[3]) % 2 == 1:
                # target is a hit circle, use raw properties
                targets.append([int(targetRaw[2]), (int(targetRaw[0]), int(targetRaw[1])), True])

            elif int(targetRaw[3]) % 4 == 2:
                # target is a slider, add start as a target
                targets.append([int(targetRaw[2]), (int(targetRaw[0]), int(targetRaw[1])), True])

                # endpoint of slider, parsed from (targetRaw[5]: curveType|curvePoints)
                endpoint = targetRaw[5].split('|')[-1].split(':')

                # sliderTime = math.dist((int(endpoint[0]), int(endpoint[1])), (int(targetRaw[0]), int(targetRaw[1]))) * int(targetRaw[6])
                # sliderTime = ((pixelLength*repeats)/(SV*100)) * beatLength
                # length / (SliderMultiplier*100)*beatLength
                sliderTime = (int(targetRaw[7]) / 180) * beatTime * int(targetRaw[6])

                # add end of slider as a non-calculated target to ensure correct distance calculation to next circle.
                # x,y,time,type,hitSound,curveType|curvePoints,slides,length,edgeSounds,edgeSets,hitSample
                if int(targetRaw[6]) % 2 == 0:
                    # Slider returns to starting point after (targetRaw[7]: length) time #int(targetRaw[2]) + int(targetRaw[7])
                    targets.append([int(targetRaw[2]) + sliderTime, (int(targetRaw[0]), int(targetRaw[1])), False])

                else:
                    # add endpoint of slider, parsed from (targetRaw[5]: curveType|curvePoints)
                    endpoint = targetRaw[5].split('|')[-1].split(':')
                    targets.append([int(targetRaw[2]) + sliderTime, (int(endpoint[0]), int(endpoint[1])), False])

            # else, target is a spinner. do not include
    
    return targets


def computeReplayStats(data):
    # beatmap file being compared to
    global beatmapLocation, beatmapFile, timingWindow, circleRadius

    # speed = 1
    if (data.mod_combination >> 6) & 1:
        # DoubleTime
        print("DT - Excluded")
        speed = 1.5
        return ["DT excluded"]
    # elif (data.mod_combination >> 8) & 1:
    #     # HalfTime
    #     print("HT")
    #     speed = 0.75
    #     return ["half-time excluded"]
    
    # the maximum time before/after a note to hit, based on replay mods
    hitWindow, hitDist, beatTime = calcDifficulty(data, 5, 7)

    with open(os.path.join(beatmapLocation, beatmapFile)) as beatmap:
        # list of hit targets and timing from beatmap
        targets = parseBeatmap(beatmap, beatTime)

        # a list of times a new key is pressed, and the position
        keyPresses = []
        # total time since play start
        timeElapsed = 0
        lastEvent = data.play_data[0]
        for index, event in enumerate(data.play_data):
            timeElapsed += event.time_since_previous_action

            if event.keys_pressed > lastEvent.keys_pressed:
                # record that a key was pressed
                keyPresses.append([timeElapsed, (event.x, 384 - event.y)])
            
            lastEvent = event

        # information for each note hit
        results = []
        
        keyIndex = 0
        miss = 0
        lastNote = targets[0]
        for t in targets:
            if t[2]:
                try:
                    # get keypresses in timing window
                    hitList = [x for x in keyPresses[keyIndex:] if x[0] >= (t[0] - hitWindow) and x[0] <= (t[0] + hitWindow) and math.dist(x[1], t[1]) < hitDist]
                except:
                    print("note missed - e")
                    miss += 1
                    continue
                
                # check that note was hit
                if not len(hitList) > 0:
                    # print("note missed")
                    miss += 1
                    continue

                hit = hitList[0]

                # record information for note hit
                # ['time', 'location', 'previous time', 'previous location', 'distance', 'period', 'hit time', 'hit location', 'accuracy', 'timing error']
                results.append([t[0], 
                    t[1], 
                    lastNote[0], 
                    lastNote[1], 
                    math.dist(t[1], lastNote[1]), 
                    (t[0] - lastNote[0]), 
                    hit[0], hit[1], 
                    math.dist(t[1], hit[1]), 
                    hit[0] - t[0]])

                # update keyIndex to reduce length of search
                keyIndex = keyPresses.index(hit, keyIndex) + 1

            lastNote = t
        
        if miss > 0:
            print("counted " + str(miss) + " missed notes")

        return results

def main():
    replayFiles = getFiles()

    with open('./replay_' + beatmapFile + '.csv', 'w', newline='') as csvFile:
        csvwriter = csv.writer(csvFile)
        csvwriter.writerow(fields)

        for replay in replayFiles:
            data = parse_replay_file(replay)
            metadata = [data.replay_id, data.replay_hash, data.game_version, data.mod_combination, "300: #" + str(data.number_300s), "100: #" + str(data.number_100s), "50: #" + str(data.number_50s), "miss: #" + str(data.misses), "Circle Size: 5", "Overall Difficulty: 7"]

            results = computeReplayStats(data)
            csvwriter.writerow(metadata)
            csvwriter.writerows(results)

    # data = parse_replay_file(replayFiles[0])    #"./Pocket Sandwich - ReoNa - SWEET HURT (TV Size) [Easy] (2021-05-07) Osu.osr")
    # results = computeReplayStats(data)

    # with open('./replayFile'+str(1)+'.csv', 'w') as csvFile:
    #     csvwriter = csv.writer(csvFile)
    #     csvwriter.writerow(fields)
    #     csvwriter.writerows(results)



if __name__ == "__main__":
    main()