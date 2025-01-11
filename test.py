hex_string = "bd1d9ddb04089700cf9c27f6f7426281"
# 先将十六进制字符串转换为字节数据
byte_data = bytes.fromhex(hex_string)
print(len(byte_data))
try:
    # 再尝试使用 UTF-8 解码
    utf8_decoded = byte_data.decode('latin-1')
    print(utf8_decoded)
except UnicodeDecodeError:
    print("无法使用 UTF-8 解码，可能该字节数据不包含有效的 UTF-8 字符")