with open('baohq-phieu-giao-nhiem-vu_23.csv', 'r', encoding='utf-8') as f:
    lines = f.readlines()

del lines[9:18]

idx = -1
for i, line in enumerate(lines):
    if line.startswith('"Nội dung 6:'):
        idx = i
        break

if idx != -1:
    lines = lines[:idx]
    
new_footer = """"Nội dung 6: Đóng gói tài liệu báo cáo và Tinh chỉnh dự án (Final Documentation),",,,,,,từ Tuần,16,đến Tuần,17,
Chi tiết (Lưu ý: Đây là nội dung bắt buộc với đồ án tốt nghiệp kỹ sư):,,,,,,,,,,
"- Mời giáo viên/người dùng trải nghiệm hệ thống và xác nhận phản hồi độ mượt UI/UX.
- Sửa lỗi đường truyền mạng (nếu có), đảm bảo hoạt động liên tục (Fail-safe).
- Biên soạn nội dung sơ đồ khối, lưu đồ thuật toán và kết luận Đồ Khóa luận.
- Định dạng lại mã nguồn và phân phối tài liệu chuẩn để bàn giao.",,,,,,,,,,
5. Lời cam đoan của sinh viên đã nhận được nhiệm vụ,,,,,,,,,,
Em xin cam kết sẽ hoàn thành các nhiệm vụ theo đúng kế hoạch.,,,,,,,,,,
,,,,,,,"Hà Nội, ngày        tháng        năm  ",,,
,,,,,,,Sinh viên,,,
,,,,,,,,,,
,,,,,,,,,,
,,,,,,,,,,
,,,,,,,Trần Đức Lê Huy,,,
,,,,,,,,,,
6. Xác nhận của giáo viên hướng dẫn về việc giao nhiệm vụ cho sinh viên,,,,,,,,,,
,,,,,,,"Hà Nội, ngày        tháng        năm  ",,,
,,,,,,,Giảng viên hướng dẫn,Giáo viên hướng dẫn,,
,,,,,,,(Ký và ghi rõ họ tên),,,
,,,,,,,,,,
,,,,,,,,,,
,,,,,,,,,,
,,,,,,,Đặng Tuấn Linh,,,
"""

lines.append(new_footer)

with open('baohq-phieu-giao-nhiem-vu_23.csv', 'w', encoding='utf-8') as f:
    f.writelines(lines)
