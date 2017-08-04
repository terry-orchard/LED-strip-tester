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
count = 0  # number of frames processed
found = []  # rough positions of found lights

# access video stream
for frame in camera.capture_continuous(raw_capture, format="bgr", use_video_port=True):
    raw = frame.array  # make frame BGR array
    if(looking):
        prev = raw
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

    
        hls = cv2.cvtColor(cropped, cv2.COLOR_BGR2HLS)

        ''' do some stuff once the lights are found '''
    else:  # if we've looked at enough frames (built up the light list)
        if(looking):  # if we just stopped looking
            if(len(found) == 25):
                print(("Found all 24 white + 1 RGB for 25 total LEDs!"))
            else:
                print(("Found only " + repr(len(found)) + " LEDs."))
            found.sort(key=lambda tup: tup[1])  # sort points top-to-bottom (by y coord)
#            for p in found:
#                print((repr(p)))  # print the list of points
            looking = 0  # done looking
        # the above code is only ran once
        ''' process all of the lights '''
        hls = cv2.cvtColor(cropped, cv2.COLOR_BGR2HLS)
        numlit = 0
        numon = 0
        for p in found:  # mark all the found points
            roi = hls[p[1] - 4:p[1] + 4, p[0] - 4:p[0] + 4]
            avg_lit = np.average(roi, axis=0)
            avg_lit = np.average(avg_lit, axis=0)
            if(avg_lit[1] >= 210):
                cv2.putText(cropped, repr(int(avg_lit[1])), (p[0] + 5, p[1]), cv2.FONT_HERSHEY_PLAIN, .5, (0, 0, avg_lit[1]))
                numlit += 1
            else:
                cv2.putText(cropped, repr(int(avg_lit[1])), (p[0] + 5, p[1]), cv2.FONT_HERSHEY_PLAIN, .5, (150, avg_lit[1], 0))
            roint = thresh[p[1] - 1:p[1] + 1, p[0] - 1:p[0] + 1]
            if(float(float(cv2.countNonZero(roint)) / 4.0) > 0.50):
                numon += 1
        '''
        if(numlit == len(found) - 1):
            print("all are lit")
            time.sleep(5)
        if(numlit >= 20):
            cv2.imshow("proc", thresh)  # display frame
            cv2.imshow("see", hls)  # display frame
            print(("total: " + repr(len(found)) + ", on = " + repr(numon) + ", lit = " + repr(numlit)))
            time.sleep(10)'''
        if(numon == 0):
            cv2.imshow("prev", prev)  # display previous frame

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
            if(led_r >= led_g and led_r >= led_b):  # if red is the largest attribute
                cv2.putText(cropped, 'RED', (rgb_led[0] + 20, rgb_led[1]), cv2.FONT_HERSHEY_PLAIN, 1, (50, 50, 250))  # red
            elif(led_g >= led_r and led_g >= led_b):  # if green is the largest attribute
                cv2.putText(cropped, 'GREEN', (rgb_led[0] + 20, rgb_led[1]), cv2.FONT_HERSHEY_PLAIN, 1, (50, 250, 50))  # green
            else:
                cv2.putText(cropped, 'BLUE', (rgb_led[0] + 20, rgb_led[1]), cv2.FONT_HERSHEY_PLAIN, 1, (250, 50, 50))  # blue
        else:
            cv2.putText(cropped, 'OFF', (rgb_led[0] + 20, rgb_led[1]), cv2.FONT_HERSHEY_PLAIN, 1, (200, 200, 200))  # not enough light, must be OFF

        cv2.putText(cropped, repr(numlit), (3, 270), cv2.FONT_HERSHEY_PLAIN, 1, (20, 10, 250))
        cv2.putText(cropped, repr(numon), (3, 285), cv2.FONT_HERSHEY_PLAIN, 1, (20, 250, 10))

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

    image = hls
    prev = image

    count += 1  # count the number of frames
    cv2.imshow("feed", image)  # display frame
    key = cv2.waitKey(1) & 0xFF  # capture a keyboard command
    raw_capture.truncate(0)  # clear current frame
    if key == ord("p"):  # press p to pause for 10s
        time.sleep(10)
    if key == ord("q"):  # press q to quit
#        print((repr(sequence)))
        break