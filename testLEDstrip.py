from picamera.array import PiRGBArray
from picamera import PiCamera
import numpy as np
import requests  # pip install requests
import time
import cv2
# initialize camera object:
camera = PiCamera()
camera.rotation = 180 # cable comes out of the "bottom" so rotate 180 deg
camera.resolution = (640, 480)
camera.framerate = 12  # turning this up too high (18+) while streaming causes glitching / more lag, can't keep up!
# camera.exposure_mode = 'spotlight' # change exposure
camera.exposure_compensation = -22  # change exposure
raw_capture = PiRGBArray(camera, size=(640, 480))  # array not image/video
time.sleep(0.1)  # warmup camera sensor

# my variables for keeping track of stuff:
looking = 1
count = 0  # number of frames processed
found = []  # rough positions of found lights

print("Press Q to quit, or P to pause and hold that frame for 10 seconds.")

# start video stream...
for frame in camera.capture_continuous(raw_capture, format="bgr", use_video_port=True):  # * B,G,R not R,G,B *
    raw = frame.array  # make frame BGR array
    if(looking):  # "looking" is true for the first 200 frames
        prev = raw  # this is for debugging // dimness testing
    ''' pre processing '''
    # NOTE: Cropping format is [y:y+h, x:x+h] **** most other coords are taken as (x,y)
    cropped = raw[40:340, 230:330]  # crop major sources of reflection out, focus on relevant area
    
    gray = cv2.cvtColor(cropped, cv2.COLOR_BGR2GRAY)  # filter out color to help with light limits
    blur = cv2.GaussianBlur(gray, (5, 5), 0)  # blurring helps with the limits between light/dark
    thresh = cv2.threshold(blur, 235, 255, cv2.THRESH_BINARY)[1]  # b/w binary image
#    cv2.imshow("proc", thresh)  # display frame (uncomment -> you can display several at the cost of a little lag)
#    edged = cv2.Canny(blur, 40, 550, 15)  # where threshed does solid shapes, edged does outlines.
    # contours
    contours = cv2.findContours(thresh.copy(), cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)[1]

    ''' build list of lights '''
    if(count < 120):  # for the first 200 frames, build up a list of lights
        for c in contours:  # go through the list of shapes
            x, y, w, h = cv2.boundingRect(c)  # bound each shape with a box
            center = (int(x + (w / 2)), int(y + (h / 2)))  # note it's rough center
            cv2.rectangle(cropped, (x, y), (x + w, y + h), (0, 0, 250), 1)  # draw the box
            if(w * h < 20):  # if the shape is small, it's an individual LED
                             # they always go small when they turn off, so this can't check dimness / intensity...
                if(len(found) == 0):  # check if we have any points yet
                    found.append(center)  # start collecting!
                else:  # check if we already have a point in *this* box
                    stored = 0  # flag for this point / LED
                    for p in found:  # go through points we already have
                        if (p[0] + 1 >= x and p[0] - 1 <= x + w and p[1] + 2 >= y and p[1] - 2 <= y + h):
                            stored = 1  # if we have a point from this box already, don't store it
                    if not(stored):
                        found.append(center)  # if not, do store it!

        ''' do some stuff once the lights are found '''
    else:  # if we've looked at enough frames (built up the LED location list)
        if(looking):  # if we *just* stopped looking do this once:
            url = "http://10.192.58.11/api/v1/device/strategy/vars/strings/status"
            creds = ('vision','rw')
            if(len(found) == 25):  # preliminary report
                data = "{\"value\":\"pass\"}"
                r = requests.post(url, data, auth=creds)
                print(("Found all 24 white + 1 RGB for 25 total LEDs!"))  # basicaly a pass (does not account for dim)
            else:
                data = "{\"value\":\"fail\"}"
                r = requests.post(url, data, auth=creds)
                print(("Found only " + repr(len(found)) + " LEDs."))  # basically a fail (does not account for dim)
            print((repr(r.status_code) + " " + r.reason))
            found.sort(key=lambda tup: tup[1])  # sort points top-to-bottom (by y coord)
#            for p in found:
#                print((repr(p)))  # print the list of points
            looking = 0  # done looking,, so the above code is only ran once

        ''' process all of the lights '''  # once all are checked and a report has been made, start processing:
        hls = cv2.cvtColor(cropped, cv2.COLOR_BGR2HLS)  # cylidrical "Hue Light Saturation" color from BGR
        numlit = 0  # how many are lit (high intensity)
        numon = 0  # how many are on (any intensity)
        for p in found:  # mark all the found points
            roi = hls[p[1] - 4:p[1] + 4, p[0] - 4:p[0] + 4]  # grab a region of interest  (ROI) around this point
            avg_lit = np.average(roi, axis=0)  # average light level across rows of pixels of the ROI
            avg_lit = np.average(avg_lit, axis=0)  # average light level across the whole ROI
            if(avg_lit[1] >= 210):  # fully lit light level is written in red
                cv2.putText(cropped, repr(int(avg_lit[1])), (p[0] + 5, p[1] - 2), cv2.FONT_HERSHEY_PLAIN, .5, (0, 0, avg_lit[1]))
                numlit += 1
            else:  # dim lights written in aqua, low lights written in blue.
                cv2.putText(cropped, repr(int(avg_lit[1])), (p[0] + 5, p[1] - 2), cv2.FONT_HERSHEY_PLAIN, .5, (150, avg_lit[1], 0))
            roint = thresh[p[1] - 1:p[1] + 1, p[0] - 1:p[0] + 1]  # check binary light level
            if(float(float(cv2.countNonZero(roint)) / 4.0) > 0.50):  # if there are mostly white pixels, it's on.
                numon += 1

        if(numon == 0):  # trying to figure out at what state we can see they're all ON for light intensity test
            cv2.imshow("prev", prev)  # display previous frame

        ''' note the color of the first LED since it's RGB '''
        rgb_led = found[0]  # the "top" light is rgb
        lit = thresh[rgb_led[1] - 1:rgb_led[1] + 1, rgb_led[0] - 1:rgb_led[0] + 1]  # get tight binary area for light
        clr = cropped[rgb_led[1] - 4:rgb_led[1] + 4, rgb_led[0] - 4:rgb_led[0] + 4]  # get small region for colour
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
            else:  # otherwise it's gotta be blue (or it's off and we don't make it this far)
                cv2.putText(cropped, 'BLUE', (rgb_led[0] + 20, rgb_led[1]), cv2.FONT_HERSHEY_PLAIN, 1, (250, 50, 50))  # blue
        else:  # if more black than white binary pixels, the light is off. because of this fork, "on" is a touch slower
            cv2.putText(cropped, 'OFF', (rgb_led[0] + 20, rgb_led[1]), cv2.FONT_HERSHEY_PLAIN, 1, (200, 200, 200))  # not enough light, must be OFF

        ''' trying to figure out how many are dim..: '''
        cv2.putText(cropped, repr(numlit), (3, 250), cv2.FONT_HERSHEY_PLAIN, 1, (20, 10, 250))  # red
        cv2.putText(cropped, repr(numon), (3, 270), cv2.FONT_HERSHEY_PLAIN, 1, (20, 250, 10))  # green
        cv2.putText(cropped, repr(numon - numlit) + " dim~", (3, 290), cv2.FONT_HERSHEY_PLAIN, 1, (200, 200, 10))

    image = cropped  # this is the type of image to be displayed (cropped/thresh/hls/blur/gray)
    prev = image  # this is for testing "all are off, what was the last thing we saw?"

    count += 1  # count the number of frames
    cv2.imshow("feed", image)  # display frame
    key = cv2.waitKey(1) & 0xFF  # capture a keyboard command
    raw_capture.truncate(0)  # clear current frame
    if key == ord("p"):  # press p to pause for 10s
        time.sleep(10)
    if key == ord("q"):  # press q to quit
#        print((repr(sequence)))
        break
