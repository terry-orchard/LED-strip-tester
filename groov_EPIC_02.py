from picamera.array import PiRGBArray
from picamera import PiCamera
import numpy as np
import time
import cv2
# initialize camera object
camera = PiCamera()
camera.resolution = (640, 480)
camera.framerate = 12
# camera.exposure_mode = 'spotlight' # change exposure
camera.exposure_compensation = -22  # change exposure
raw_capture = PiRGBArray(camera, size=(640, 480))  # array not image/video
time.sleep(0.1)  # warmup camera sensor

# my variables for keeping track of stuff:
looking = 1
measuring = 0
count = 0  # number of frames processed
found = []  # rough positions of found lights
status = []
#record = 0
#prevlit = 0
#sequence = []
# access video stream
for frame in camera.capture_continuous(raw_capture, format="bgr", use_video_port=True):
    raw = frame.array  # make frame BGR array

    ''' pre processing '''
    cropped = raw[40:340, 250:350]
    gray = cv2.cvtColor(cropped, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (5, 5), 0)
    thresh = cv2.threshold(blur, 235, 255, cv2.THRESH_BINARY)[1]
#    cv2.imshow("proc", thresh)  # display frame
#    edged = cv2.Canny(blur, 40, 550, 15)
    contours = cv2.findContours(thresh.copy(), cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)[1]

    ''' build list of lights '''
    if(count < 200):  # for the first 200 frames, build up a list of lights
        for c in contours:
            x, y, w, h = cv2.boundingRect(c)  # bound each shape
            center = (int(x + (w / 2)), int(y + (h / 2)))  # note it's rough center
            cv2.rectangle(cropped, (x, y), (x + w, y + h), (0, 0, 250), 1)  # draw the rectangle
            if(w * h < 20):  # if the shape is small
                if(len(found) == 0):
                    found.append(center)  # check if we have any points yet
                else:  # check if we already have a point in *this* box
                    stored = 0  # flag for this box
                    for p in found:  # go through points we already have
                        if (p[0] + 1 >= x and p[0] - 1 <= x + w and p[1] + 2 >= y and p[1] - 2 <= y + h):
                            stored = 1  # if so, don't store it
                    if not(stored):
                        found.append(center)  # if not, store it

        ''' do some stuff once the lights are found '''
    else:  # if we've looked at enough frames (built up the light list)
        if(looking):  # if we just stopped looking
            print(("found " + repr(len(found)) + " LEDs!"))
            found.sort(key=lambda tup: tup[1])  # sort points top-to-bottom
#            for p in found:
#                print((repr(p)))  # print the list of points
            looking = 0  # done looking

            lengths = []  # list the distance (in pixels) between each light and the next
            for p in range(2, len(found)):  # don't check light #0 (rgb)
                thisl = found[p]
                lastl = found[p - 1]
                lengths.append(thisl[1] - lastl[1])  # record length
            avglen = np.average(lengths)  # average distance
            print((repr(avglen)))  # d e b u g g i n g i s f u n
            findex = 1  # track index of found LEDs (their position in the array)
            lednum = 1  # track index of real LEDs (their # on the board)
            status.append((lednum, 1, found[findex][1]))  # assume the first is OK.... have to start somewhere <--
            for l in lengths:  # go through the distances
                lednum += 1
                missing = int(float(l) / float(avglen + 1))  # if the gap is big enough for missing lights,
                for miss in range(missing):  # note the missing lights
                    status.append((lednum, 0, -1))  # .append(LED number, state, y-coord)
                    lednum += 1
                status.append((lednum, 1, found[findex][1]))  # note the light at the other end of this length
                findex += 1
            print("Press R when all are on to snapshot and measure on/dim/dead")  # Plan to automate trigger...
#            measuring = 1  # now you can check the light level of all the found lights
            ''' the above code is done only once '''

        ''' process all of the lights '''
        hls = cv2.cvtColor(cropped, cv2.COLOR_BGR2HLS)
#        numlit = 0
        for p in found:  # mark all the found points
            roi = hls[p[1] - 4:p[1] + 4, p[0] - 4:p[0] + 4]
            avg_lit = np.average(roi, axis=0)
            avg_lit = np.average(avg_lit, axis=0)
            if(avg_lit[1] >= 210):
                cv2.putText(cropped, repr(int(avg_lit[1])), (p[0] + 5, p[1]), cv2.FONT_HERSHEY_PLAIN, .5, (0, 0, avg_lit[1]))
#                numlit += 1
            else:
                cv2.putText(cropped, repr(int(avg_lit[1])), (p[0] + 5, p[1]), cv2.FONT_HERSHEY_PLAIN, .5, (150, avg_lit[1], 0))
#            if(measuring):
#                roint = thresh[p[1] - 2:p[1] + 2, p[0] - 2:p[0] + 2]
#                if(float(float(cv2.countNonZero(roint)) / float(16)) > 0.50):
#                    numlit += 1
        '''
        if(numlit == (len(found) - 1) and measuring):
            for p in found:  # check each found point
                roi = hls[p[1] - 4:p[1] + 4, p[0] - 4:p[0] + 4]
                avg_lit = np.average(roi, axis=0)
                avg_lit = np.average(avg_lit, axis=0)
                if(avg_lit[1] < 200):
                    sindex = 0  # status index
                    for q in status:
                        if(q[2] == p[1]):  # if they having matching y coords, we're at that light
                            status[sindex] = (q[0], 2, q[2])  # mark it as dim
                        sindex += 1
            for s in status:
                print((repr(s[0]) + " : " + repr(s[1])))
            measuring = 0  # done measuring
            '''

        ''' note the color of the first LED since it's RGB '''
        rgb_led = found[0]
        lit = thresh[rgb_led[1] - 1:rgb_led[1] + 1, rgb_led[0] - 1:rgb_led[0] + 1]  # get binary light level
        clr = cropped[rgb_led[1] - 4:rgb_led[1] + 4, rgb_led[0] - 4:rgb_led[0] + 4]  # get region data for colour
        if(float(float(cv2.countNonZero(lit)) / float(4)) > 0.50):  # if more light than dark, it's ON
            row_avg = np.average(clr, axis=0)  # average pixel color by row
            tot_avg = np.average(row_avg, axis=0)  # total average pixel color
            led_b = tot_avg[0]  # average color attribute BLUE
            led_g = tot_avg[1]  # average color attribute GREEN
            led_r = tot_avg[2]  # average color attribute RED
            if(led_r >= led_g and led_r >= led_b):
                cv2.putText(cropped, 'RED', (rgb_led[0] + 20, rgb_led[1]), cv2.FONT_HERSHEY_PLAIN, 1, (50, 50, 250))  # red
            elif(led_g >= led_r and led_g >= led_b):
                cv2.putText(cropped, 'GREEN', (rgb_led[0] + 20, rgb_led[1]), cv2.FONT_HERSHEY_PLAIN, 1, (50, 250, 50))  # green
            else:
                cv2.putText(cropped, 'BLUE', (rgb_led[0] + 20, rgb_led[1]), cv2.FONT_HERSHEY_PLAIN, 1, (250, 50, 50))  # blue
        else:
            cv2.putText(cropped, 'OFF', (rgb_led[0] + 20, rgb_led[1]), cv2.FONT_HERSHEY_PLAIN, 1, (200, 200, 200))  # not enough light, must be OFF

    '''
#        cv2.putText(cropped, '#'+repr(numlit), (5,270), cv2.FONT_HERSHEY_PLAIN, 1, (20,10,250))
        if(numlit == 0 and not record):
            print("previous: "+repr(prevlit)+", now: "+repr(numlit)) # cv2.putText(cropped, "ZERO NOW", (1,10), cv2.FONT_HERSHEY_PLAIN, 1, (0,0,250))
            if(prevlit == 24): record = 1
#        sublist = list(found)
#        sublist.pop(0) '''
    ''' try to record light sequence '''
    '''        if(not record and not numlit and prevlit == 24):
            record = 1
        prevlit = numlit
        if(record and len(sequence) < 45):
            cv2.putText(cropped, "o", (80, 15), cv2.FONT_HERSHEY_PLAIN, 2, (0, 0, 250))
            i = 0
            for p in found:
                roi = hls[p[1] - 4:p[1] + 4, p[0] - 4:p[0] + 4]
                avg_lit = np.average(roi, axis=0)
                avg_lit = np.average(avg_lit, axis=0)
                if(avg_lit[1] >= 200 and not i == 0):
                    sequence.append(i)
                    break
                i += 1 '''

    image = cropped
    count += 1  # count the number of frames
    cv2.imshow("feed", image)  # display frame
    key = cv2.waitKey(1) & 0xFF  # capture a keyboard command
    raw_capture.truncate(0)  # clear current frame
    if key == ord("r"):

        state = ['dead', 'on  ', 'dim ']
        for led in status:
            print(("# " + repr(led[0]) + "\t" + state[led[1]] + " @ " + repr(led[2])))
        temp = list(found)
        temp.pop(0)
        for p in temp:  # check each found point
            roi = hls[p[1] - 4:p[1] + 4, p[0] - 4:p[0] + 4]
            avg_lit = np.average(roi, axis=0)
            avg_lit = np.average(avg_lit, axis=0)
            if(avg_lit[1] < 210):
                sindex = 0  # status index
                for q in status:
                    if(q[2] == p[1]):  # if they having matching y coords, we're at that light
                        status[sindex] = (q[0], 2, q[2])  # mark it as dim
                    sindex += 1
        print("Dead LEDs: ", end="")
        for s in status:
            if(s[1] == 0):
                print((repr(s[0])), end=", ")
        print("")
        print("Dim LEDs: ", end="")
        dimcount = 0
        for s in status:
            if(s[1] == 2):
                print((repr(s[0])), end=", ")
                dimcount += 1
        print("")
        print(("The other " + repr(len(found) - dimcount - 1) + " are OK!\n"))
        for led in status:
            print(("# " + repr(led[0]) + "\t" + state[led[1]] + " @ " + repr(led[2])))
        cv2.imshow("snapshot", cropped)  # display snapshot in it's own window
#        time.sleep(5)

    if key == ord("p"):  # press p to pause for 10s
        time.sleep(10)
    if key == ord("q"):  # press q to quit
#        print((repr(sequence)))
        break