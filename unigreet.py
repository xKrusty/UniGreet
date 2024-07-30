from PIL import Image, ImageChops, ImageFilter, ImageOps
from enum import Enum
import numpy as np
import argparse
import random
import math
import time
import sys
import os

class Charset(Enum):
    BLOCK = "BLOCK"
    BRAILLE = "BRAILLE"

class HAlignment(Enum):
    LEFT = "LEFT"
    CENTER = "CENTER"
    RIGHT = "RIGHT"

class VAlignment(Enum):
    TOP = "TOP"
    CENTER = "CENTER"
    BOTTOM = "BOTTOM"

class Writer():
    def __init__(self, file: str):
        self.file = open(file, "bw")
        self.stdout = sys.stdout
    
    def write(self, message):
        self.stdout.write(message)
        
        message = str.encode(message, "utf-16")
        self.file.write(message)
    
    def flush(self):
        self.file.flush()
        self.stdout.flush()
    
    def __del__(self):
        self.file.close()

def limit_type(i):
    i = int(i)
    if i < 0 or i > 256:
        raise argparse.ArgumentTypeError("Invalid limit, value needs to be in Range [0, 256]")
    return i

def is_asgi_file(file):
    if not file.endswith(".asgi"):
        raise argparse.ArgumentTypeError("Invalid file provided. File must have .asgi extension")
    return file

def is_valid_dir(path):
    if not os.path.isdir(path):
        raise argparse.ArgumentTypeError("Invalid path provided")
    return path

def trim_whitespace(img):
    bg = Image.new(img.mode, img.size, img.getpixel((0,0)))

    diff = ImageChops.difference(img, bg)
    bbox = diff.getbbox()

    if bbox:
        return img.crop(bbox)
    return img

def calculate_new_size(img, size, charset):
    width, height = img.size

    new_height = size

    hpercent = new_height / height

    new_width = int(width * hpercent)

    if (new_height == 0):
        new_height = 1
    if (new_width == 0):
        new_width = 1

    scale = (1, 1)
    if charset == Charset.BLOCK:
        scale = (4,2) # 4 because characters are twice as height as they are broad
    elif charset == Charset.BRAILLE:
        scale = (4,4)

    new_size = (int(new_width*scale[0]), new_height*scale[1])
    return new_size

def calculate_fill_size(img, args):
    # calculate fill sizes
    screen_size = os.get_terminal_size()

    new_size = calculate_new_size(img, screen_size[1], args.charset)

    i = 1
    while new_size[0]*(2 if args.charset == Charset.BRAILLE else 1) > screen_size[0] or new_size[1] > screen_size[1]:
        s = screen_size[1] - i
        i += 1
        new_size = calculate_new_size(img, s, args.charset)
    
    return new_size[1]


def resize_img(img, size, charset):
    new_size = calculate_new_size(img, size, charset)
    img2 = img.resize(new_size)
    return img2

def print_img(img, args):
    # get args
    threshold = args.threshold
    invert = args.invert
    charset = args.charset
    horizontal_alignment = args.horizontal_align
    vertical_alignment = args.vertical_align
    padding = args.padding
    print_in_color = args.nocolor
    limit = args.limit
    upper_threshold = args.upperthreshold
    DEBUG = args.DEBUG


    # function start
    width, height = img.size

    if DEBUG:
        img.save("tmp.png")

    # limit color pallete
    if limit > 0:
        img = img.convert('P').quantize(colors=limit, dither=Image.Dither.FLOYDSTEINBERG, method=Image.MEDIANCUT).convert("RGB")
        # img = img.convert('P', colors=limit, palette=Image.ADAPTIVE).convert("RGB")

    if DEBUG:
        img.save("tmp_limit.png")

    # get grayscale representation for threshold
    img_gray = img.convert("L")
    if invert:
        img_gray = ImageChops.invert(img_gray)

    if DEBUG:
        img_gray.save("tmp_gray.png")

    # get terminal screen size
    screen_size = os.get_terminal_size()
    img_size = img.size

    # get window size for selected charset
    height_step = 1
    width_step = 1
    if charset == Charset.BLOCK:
        height_step = 2
        width_step = 2
    if charset == Charset.BRAILLE:
        height_step = 4
        width_step = 2

    # get horizontal / vertical padding
    print_size = (img_size[0] / width_step, img_size[1] / height_step)
    horizontal_padding = 0
    if horizontal_alignment == HAlignment.LEFT:
        horizontal_padding = 0
    if horizontal_alignment == HAlignment.CENTER:
        horizontal_padding = int((screen_size[0]/2) - (print_size[0]/2))
    if horizontal_alignment == HAlignment.RIGHT:
        horizontal_padding = int(screen_size[0] - print_size[0])
    
    vertical_padding_top = 0
    vertical_padding_bottom = 0
    if padding - print_size[1] > 0: # only add padding when its greater than the print height
        if vertical_alignment == VAlignment.TOP:
            vertical_padding_top = 0
            vertical_padding_bottom = int(padding - print_size[1])
        if vertical_alignment == VAlignment.CENTER:
            tmp = padding - print_size[1]
            vertical_padding_top = int(math.ceil(tmp / 2.0))
            vertical_padding_bottom = int(math.floor(tmp / 2.0))
        if vertical_alignment == VAlignment.BOTTOM:
            vertical_padding_bottom = 0
            vertical_padding_top = int(padding - print_size[1])

    pixels = img_gray.load()
    # pixels = np.array(img_gray)
    color_pixels = img.load()

    print("\n"*vertical_padding_top, end='')

    prev_color = None
    if charset == Charset.BLOCK:
        # block_str = " ▘▝▀▖▌▞▛▗▚▐▜▄▙▟█"

        for j in range(0, height, height_step):
            #padding
            print(" "*horizontal_padding, end='')

            for i in range(0, width, width_step):
                color = (0,0,0)
                if len(img.getbands()) > 1: # Handle RGB
                    p = (color_pixels[i, j], color_pixels[i+1, j], color_pixels[i, j+1], color_pixels[i+1, j+1])
                    count = len([c for c in p if any(v > threshold for v in c[:3])]) # number of pixels that are above threshold
                    if count == 0:
                        color = (0,0,0)
                    else:
                        color = [int(sum(c)/count) for c in zip(*p)]
                else: # Handle Grayscale
                    color = int((color_pixels[i, j] + color_pixels[i+1, j] + color_pixels[i, j+1] + color_pixels[i+1, j+1]) / 4.0)
                    color = [color]*3
                
                if print_in_color:
                    if color != prev_color:
                        print(f"\x1B[38;2;{color[0]};{color[1]};{color[2]}m", end='')
                        prev_color = color

                # this is actually slower in python :(
                # window = pixels[j:j+2, i:i+2] # Numpy matrix uses height x width, instead of width x height like PIL does
                # window = window.flatten(order='C')
                # boolean_array = window > threshold
                # byte_value = np.packbits(boolean_array, bitorder='little')[0]
                # print(block_str[byte_value], end='')

                # order matters (this can be optimized if i used numpy matrix and then check for a submatrix, would be easier)
                if pixels[i, j] > threshold and pixels[i+1, j] > threshold and pixels[i, j+1] > threshold and pixels[i+1, j+1] > threshold:
                    print("█", end='')
                elif pixels[i, j] > threshold and pixels[i+1, j] > threshold and pixels[i, j+1] > threshold:
                    print("▛", end='')
                elif pixels[i, j] > threshold and pixels[i, j+1] > threshold and pixels[i+1, j+1] > threshold:
                    print("▙", end='')
                elif pixels[i, j] > threshold and pixels[i+1, j] > threshold and pixels[i+1, j+1] > threshold:
                    print("▜", end='')
                elif pixels[i+1, j] > threshold and pixels[i, j+1] > threshold and pixels[i+1, j+1] > threshold:
                    print("▟", end='')
                elif pixels[i, j] > threshold and pixels[i+1, j+1] > threshold:
                    print("▚", end='')
                elif pixels[i+1, j] > threshold and pixels[i, j+1] > threshold:
                    print("▞", end='')
                elif pixels[i, j] > threshold and pixels[i+1, j] > threshold:
                    print("▀", end='')
                elif pixels[i, j+1] > threshold and pixels[i+1, j+1] > threshold:
                    print("▄", end='')
                elif pixels[i, j] > threshold and pixels[i, j+1] > threshold:
                    print("▌", end='')
                elif pixels[i+1, j] > threshold and pixels[i+1, j+1] > threshold:
                    print("▐", end='')
                elif pixels[i, j] > threshold:
                    print("▘", end='')
                elif pixels[i+1, j] > threshold:
                    print("▝", end='')
                elif pixels[i, j+1] > threshold:
                    print("▖", end='')
                elif pixels[i+1, j+1] > threshold:
                    print("▗", end='')
                else:
                    print(" ", end='')
            print("")

    if charset == Charset.BRAILLE:
        # corresponding braille patterns
        braille_str = "⠀⠁⠂⠃⠄⠅⠆⠇⠈⠉⠊⠋⠌⠍⠎⠏⠐⠑⠒⠓⠔⠕⠖⠗⠘⠙⠚⠛⠜⠝⠞⠟⠠⠡⠢⠣⠤⠥⠦⠧⠨⠩⠪⠫⠬⠭⠮⠯⠰⠱⠲⠳⠴⠵⠶⠷⠸⠹⠺⠻⠼⠽⠾⠿⡀⡁⡂⡃⡄⡅⡆⡇⡈⡉⡊⡋⡌⡍⡎⡏⡐⡑⡒⡓⡔⡕⡖⡗⡘⡙⡚⡛⡜⡝⡞⡟⡠⡡⡢⡣⡤⡥⡦⡧⡨⡩⡪⡫⡬⡭⡮⡯⡰⡱⡲⡳⡴⡵⡶⡷⡸⡹⡺⡻⡼⡽⡾⡿⢀⢁⢂⢃⢄⢅⢆⢇⢈⢉⢊⢋⢌⢍⢎⢏⢐⢑⢒⢓⢔⢕⢖⢗⢘⢙⢚⢛⢜⢝⢞⢟⢠⢡⢢⢣⢤⢥⢦⢧⢨⢩⢪⢫⢬⢭⢮⢯⢰⢱⢲⢳⢴⢵⢶⢷⢸⢹⢺⢻⢼⢽⢾⢿⣀⣁⣂⣃⣄⣅⣆⣇⣈⣉⣊⣋⣌⣍⣎⣏⣐⣑⣒⣓⣔⣕⣖⣗⣘⣙⣚⣛⣜⣝⣞⣟⣠⣡⣢⣣⣤⣥⣦⣧⣨⣩⣪⣫⣬⣭⣮⣯⣰⣱⣲⣳⣴⣵⣶⣷⣸⣹⣺⣻⣼⣽⣾⣿"

        pixels = np.array(img_gray)
        color_pixels = np.array(img)
        for j in range(0, height, height_step):
            #padding
            print(" "*horizontal_padding, end='')

            for i in range(0, width, width_step):
                # get color (this should ignore colors below threshold)
                color_window = color_pixels[j:j+height_step, i:i+width_step]
                # get all pixels that are above threshold, ignore Alpha channel
                color = (0,0,0)
                # if len(color_pixels.shape) == 3 and color_pixels.shape[2] == 4: # for images with RGBA
                #     # remove images with alpha below threshold, to not mess up the colors (theshold should be set with a separate flag)
                #     mask = color_window[:,:,3] > 254
                #     color_window[~mask] = [0,0,0,0]
                if len(color_pixels.shape) > 2: # handle RGB image
                    color_window = color_window[np.any(color_window[..., :3], axis=2)] 
                    if color_window.shape[0] > 0: # has at least one pixel above threshold
                        color = (color_window.sum(axis=0) / color_window.shape[0]).astype(int)
                else: # handle Grayscale
                    color_window = color_window[np.any(color_window > threshold & color_window < upper_threshold, axis=1)]
                    if color_window.shape[0] > 0: # has at least one pixel above threshold
                        color = (color_window.sum(axis=1) / color_window.shape[0]).astype(int)
                        color = np.repeat(color, 3)
                    
                # if image is RGBA
                if len(color) > 3:
                    color = color[:3]

                if print_in_color:
                    if not np.all(np.equal(color, prev_color)):
                        print(f"\x1B[38;2;{color[0]};{color[1]};{color[2]}m", end='')
                        prev_color = color

                window = pixels[j:j+4, i:i+2] # Numpy matrix uses height x width, instead of width x height like PIL does

                # if len(pixels.shape) == 3 and pixels.shape[2] == 4: # for images with RGBA
                #     # remove images with alpha below threshold, to not mess up the colors (theshold should be set with a separate flag)
                #     mask = window[:,:,3] > 254
                #     window[~mask] = [0,0,0,0]

                # transform window into 1 byte and index into braille_str (as the str is in order)
                window = window.flatten(order='F')
                window = window[::-1] # reverse order
                # create correct order, because Braill order is different:
                # left-column is: 1,2,3,7 and right-column is: 4,5,6,8⠀
                window[1], window[4] = window[4], window[1]
                window[2], window[4] = window[4], window[2]
                window[3], window[4] = window[4], window[3]
                # boolean_array = window > threshold
                boolean_array = np.logical_and(window > threshold, window < upper_threshold)
                byte_value = np.packbits(boolean_array)[0]
                print(braille_str[byte_value], end='')

            print("")

    print("\x1B[0m", end='')
    print("\n"*vertical_padding_bottom, end='')

def load_from_file(file):
    with open(file, 'rb') as f:
        while True:
            c = f.read(2)
            if c == b'': # EOF
                break
            if c == b'\x1b\x00':
                c = c[0].to_bytes(1)
                for i in range(0, 20):
                    c += f.read(2)
                    c = c[:-1] # second char read will always be 0x00
                    if chr(c[-1]) == "m":
                        break
                    if i == 19:
                        print(f"\x1B[0m\nCorrupted .asgi file. Exiting. (pos: {f.tell()})")
                        return
                print(c.decode("utf-8"), end='')
                continue # continue to next char (prevent printing escape-sequence in utf-16)
            print(c.decode("utf-16"), end='')

def convert_and_print(args, parser):
    img = Image.open(args.file)

    # crop the image
    if args.crop:
        img = trim_whitespace(img)

    # calculate the fill size
    if args.fill:
        args.size = calculate_fill_size(img, args)

    img2 = resize_img(img, args.size, args.charset)

    # prepare save file
    if args.save != None:
        # check if directory exists
        directory = os.path.dirname(args.save)
        if directory == "." or directory == "":
            directory = os.getcwd()
        if not os.path.isdir(directory):
            parser.error("Directory for provided '--save' path not found")
        
        # check file name
        file = os.path.basename(args.save)
        ext = ".asgi"
        if file == "":
            file = os.path.basename(args.file)
            file = os.path.splitext(file)[0]
            file += ext # change the file extension if using original file name (e.g. .png changes to .asgi)
        else:
            file += ext

        save_file_path = os.path.join(directory, file)
        print(f"SAVING: {save_file_path}, file: {file}, dir: {directory}, ext: {ext}")

        # set stdout to stdout + a file handle
        sys.stdout = Writer(save_file_path)

    # print image
    print_img(img2, args)

def main():
    parser = argparse.ArgumentParser(prog="UniGreet", description="Converts Images to different Unicode sets, with colors and more")

    parser.add_argument('file', nargs='?')
    parser.add_argument('-s', '--size', type=int, default=30, help="sets the image size in lines, e.g. 30 = output is 30 lines in height")
    parser.add_argument('-t', '--threshold', type=int, default=0, help="sets a threshold to ignore values that are darker than the set value")
    parser.add_argument('-ut', '--upperthreshold', type=int, default=256, help="sets a upper threshold to ignore values that are lighter than the set value")
    parser.add_argument('-c', '--charset', type=Charset, default=Charset.BLOCK, choices=list(Charset), help="select the charset that the image should be printed as")
    parser.add_argument('-i', '--invert', action='store_true', help="inverts the grayscale-representation of the image, this is useful for images with white backgrounds, to cut them out")
    parser.add_argument('--time', action='store_true', help="measures the time it takes to print the image out")
    parser.add_argument('-ha', '--horizontal-align', type=HAlignment, default=HAlignment.CENTER, choices=list(HAlignment), help="sets the horizontal alignment for where the image should be printed")
    parser.add_argument('-va', '--vertical-align', type=VAlignment, default=VAlignment.CENTER, choices=list(VAlignment), help="sets the vertical alignment for where the image should be printed. This Option only has effect when paired with padding")
    parser.add_argument('-p', '--padding', type=int, default=0, help="Sets a vertical padding to the result in lines. This is the total count of lines for the output (so e.g. size is 30, padding is 40, then the output is 40 lines, 10 of which are empty). If the padding is lower than the print height, then it is ignored. This option can be paired with vertical-align.")
    parser.add_argument('--nocolor', action='store_false', help="Prints the image without colors")
    parser.add_argument('-l', '--limit', type=limit_type, help="limit the picture to a set amount of colors", default=0)
    parser.add_argument('--crop', action='store_true', help="Trim empty transparent parts of an image.")
    parser.add_argument('--fill', action='store_true', help="This lets the print fill out the entire space of the current terminal window. It overwrites the --size and --padding values. a Alignment and --crop can still be applied")
    parser.add_argument('--DEBUG', action='store_true', help="saves debug images")
    parser.add_argument('--save', const="", nargs='?', help="saves image as a text-file, that way you can save your settings. If no filename provided the file will take the original file name. The stored file will have a .asgi extension")
    parser.add_argument('--load', type=is_asgi_file, help="Load a .asgi file instead of an image")
    parser.add_argument('--load-random', type=is_valid_dir, help="Loads a random .asgi file from a provided directory")
    args = parser.parse_args()

    if (args.load != None or args.load_random != None) and args.file:
        parser.error("The '--load' and '--load-random' flag cannot be used with a 'file' argument")
    elif not args.load and not args.load_random and not args.file:
        parser.error("The following argument is required: 'file' or '--load' or '--load-random'")

    s1 = time.time()
    ms1 = time.time_ns() // 1_000_000

    # load file if flag set
    if args.load != None:
        load_from_file(args.load)
    # load random file if flag set
    elif args.load_random != None:
        files = os.listdir(args.load_random)
        files = [f for f in files if f.endswith(".asgi")]
        if len(files) == 0:
            parser.error("Provided path has no .asgi files")
        rand_file = random.choice(files)
        rand_path = os.path.join(args.load_random, rand_file)
        load_from_file(rand_path)
    # convert image and print
    else:
        convert_and_print(args, parser)

    s2 = time.time()
    ms2 = time.time_ns() // 1_000_000

    if args.time:
        print(f"{s2-s1:.2f}s, {ms2-ms1:.2f}ms")

if __name__ == '__main__':
    main()
