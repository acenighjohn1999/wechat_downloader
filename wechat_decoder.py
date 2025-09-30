import os

# Base folder containing all user folders
input_folder = r"C:\Users\henry\Documents\WeChat Files\wxid_5zk2tbe173ua22\FileStorage\MsgAttach"

# Output folder for decoded images
output_base = r"C:\Users\henry\Documents\WeChat Decoded Images"
os.makedirs(output_base, exist_ok=True)


def decode_wechat_dat(input_path, output_path):
    with open(input_path, "rb") as f:
        data = bytearray(f.read())

    # Guess XOR key using first byte
    key = data[0] ^ 0xFF

    # Decode
    for i in range(len(data)):
        data[i] ^= key

    with open(output_path, "wb") as f:
        f.write(data)

for user_folder in os.listdir(input_folder):
    user_path = os.path.join(input_folder, user_folder)
    if not os.path.isdir(user_path):
        continue

    image_root = os.path.join(user_path, "Image")
    if not os.path.exists(image_root):
        continue

    # Iterate over all month folders inside Image/
    for month_folder in os.listdir(image_root):
        month_path = os.path.join(image_root, month_folder)
        if not os.path.isdir(month_path):
            continue

        for file_name in os.listdir(month_path):
            if file_name.lower().endswith(".dat"):
                input_file = os.path.join(month_path, file_name)

                # Create corresponding output path
                output_folder = os.path.join(output_base, user_folder, "Image", month_folder)
                os.makedirs(output_folder, exist_ok=True)
                output_file = os.path.join(output_folder, file_name.replace(".dat", ".jpg"))

                decode_wechat_dat(input_file, output_file)
                print(f"Decoded: {input_file} -> {output_file}")