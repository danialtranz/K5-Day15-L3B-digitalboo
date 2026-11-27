# Digitalboo · Hướng dẫn demo

## Chuẩn bị

1. Từ thư mục gốc của repo, chạy lệnh sau.

   ```sh
   python3 -m http.server 8765 --bind 127.0.0.1 --directory frontend
   ```

2. Mở [Digitalboo tại localhost](http://127.0.0.1:8765/).
3. Với mỗi kịch bản bên dưới, mở **Chế độ demo** ở cuối thanh bên, chọn đúng tên rồi bấm **Bắt đầu kịch bản**. **Tổng quan** mở dashboard. Các kịch bản Standup và Outlook mở chat và gửi yêu cầu mẫu tự động.

Chọn lại cùng kịch bản và bấm **Bắt đầu kịch bản** để chạy lại từ đầu. **Đặt lại dữ liệu → Đặt lại** khôi phục dữ liệu ban đầu của kịch bản hiện tại và đưa bạn về dashboard. Bắt đầu hoặc đặt lại kịch bản sẽ thay thế cuộc trò chuyện, tác vụ và thông báo của phiên demo trước.

Toàn bộ kết nối, email và nộp bài dùng dữ liệu mô phỏng. Trong cửa sổ đăng nhập, bấm nút xác nhận bằng tài khoản mẫu. Nếu cửa sổ riêng không hiện, dùng **Tiếp tục tại đây** hoặc **Hoàn tất kết nối** trong tab chính.

Giờ hẹn hiển thị theo giờ Việt Nam (UTC+7). Giữ tab mở nếu muốn đợi tác vụ đến hạn. Dùng **Chạy mô phỏng** để trình diễn ngay sau khi đặt lịch.

## Tổng quan

### 01. Tổng quan

1. Trên dashboard, chỉ vào thẻ **Daily Standup**, **Email quan trọng** và **Chờ xác nhận**. Kéo xuống **Tài khoản kết nối** để xem Phoenix và Outlook.
2. Bấm **Chuẩn bị Standup** để mở cuộc trò chuyện có bản nháp chờ duyệt.
3. Quay lại **Tổng quan**, bấm **Xem tổng hợp** trong **Email cần chú ý**. Mở **Tác vụ** để xem lời nhắc họp đồng bộ đã lên lịch. Mở **Thông báo** và chọn **Daily Standup đang chờ duyệt** để quay về tác vụ và cuộc trò chuyện liên quan.

**Dấu hiệu đạt** — Dashboard có 3 email quan trọng, 1 tác vụ chờ xác nhận và 2 tài khoản đã kết nối. Bản nháp, báo cáo Outlook và lời nhắc mở được từ các mục tương ứng.

## Daily Standup

Các kịch bản nộp dùng cùng một chuỗi thao tác: **Dùng ghi chú mẫu → Xác nhận và đặt lịch → Xác nhận lịch → Chạy mô phỏng**. Giữ ngày giờ mặc định hoặc chọn một thời điểm trong tương lai.

### 02. Standup · Thành công

1. Bấm **Dùng ghi chú mẫu**. Trong bản nháp, bấm **Chỉnh sửa**, sửa một dòng rồi **Lưu ghi chú**.
2. Bấm **Xác nhận và đặt lịch → Xác nhận lịch**. Chỉ vào trạng thái **Đã lên lịch**. Có thể mở **Sửa lịch** để đổi giờ và bấm **Lưu lịch mới**.
3. Bấm **Chạy mô phỏng**. Mở **Thông báo** để xem **Đã nộp Daily Standup** và **Tác vụ → Hoàn thành** để xem kết quả.

**Dấu hiệu đạt** — Bản nháp giữ nội dung đã chỉnh sửa. Chat chuyển qua **Đang nộp** rồi **Nộp thành công**. Tác vụ đã thành công không còn nút chạy lại.

### 03. Standup · Thiếu thông tin

1. Bấm **Hôm qua không có việc**. Chờ agent báo chưa thể hoàn thành Daily Standup.
2. Bấm **Nhập ghi chú**. Điền **Việc đã làm hôm qua** bằng nội dung mẫu `Hoàn thiện bảng kiểm thử đăng nhập.` Để trống **Kế hoạch ngày mai** rồi **Lưu ghi chú**.
3. Bấm **Chưa có kế hoạch ngày mai → Tôi sẽ bổ sung sau** để xem phản hồi chờ bổ sung.
4. Bấm lại **Chưa có kế hoạch ngày mai → Gợi ý từ công việc hôm qua**. Mở **Chỉnh sửa** để sửa kế hoạch gợi ý trước khi duyệt.

**Dấu hiệu đạt** — Agent không tự tạo công việc hôm qua. Sau khi đã có nội dung hôm qua, agent chỉ hỏi thêm kế hoạch ngày mai và tạo bản nháp khi người dùng bổ sung hoặc đồng ý xem gợi ý.

### 04. Standup · Phiên hết hạn

1. Khi chat báo phiên Phoenix hết hạn, bấm **Đăng nhập Phoenix**.
2. Trong cửa sổ mô phỏng, bấm **Hoàn tất đăng nhập**. Quay về chat.
3. Bấm **Dùng ghi chú mẫu**, duyệt và đặt lịch. Dùng **Chạy mô phỏng** nếu cần trình diễn đến lúc nộp xong.

**Dấu hiệu đạt** — Agent tiếp tục yêu cầu cũ và hỏi thông tin hôm qua, ngày mai ngay sau khi kết nối lại. Người dùng không phải gửi lại yêu cầu Standup.

### 05. Standup · Lỗi mạng

1. Dùng ghi chú mẫu, xác nhận lịch và bấm **Chạy mô phỏng**.
2. Chờ trạng thái **Nộp thất bại**. Mở **Thông báo**, chọn **Nộp Daily Standup thất bại** để mở chi tiết tác vụ và chat liên quan.
3. Bấm **Thử lại** trên tác vụ đó.

**Dấu hiệu đạt** — Chat và thông báo đều ghi “Mất kết nối mạng khi gửi bản Daily Standup.” Tác vụ cũ chuyển sang **Nộp thành công** sau khi thử lại.

### 06. Standup · Lỗi Phoenix

1. Dùng ghi chú mẫu, xác nhận lịch và bấm **Chạy mô phỏng**.
2. Chờ lỗi “Phoenix trả về lỗi trong lúc tiếp nhận bản Daily Standup.” Mở **Tác vụ → Thất bại** để tìm bản nộp.
3. Mở chi tiết, bấm **Thử lại**. Khi thấy **Nộp thành công**, mở **Tác vụ → Lịch sử hoạt động**.

**Dấu hiệu đạt** — Chi tiết tác vụ ghi đúng lỗi từ Phoenix. Lịch sử có cả lần thất bại và lần nộp thành công sau khi thử lại.

### 07. Standup · Phiên hết hạn khi nộp

1. Dùng ghi chú mẫu và đặt lịch khi Phoenix còn kết nối. Bấm **Chạy mô phỏng**.
2. Sau khi lần nộp thất bại, mở thông báo tương ứng hoặc bấm **Đăng nhập và thử lại** trong chat.
3. Bấm **Hoàn tất đăng nhập** trong cửa sổ mô phỏng. Quay về chat và chờ tác vụ chạy lại.

**Dấu hiệu đạt** — Lỗi xuất hiện ở bước nộp và ghi rõ phiên Phoenix hết hạn. Sau khi đăng nhập lại, agent thử lại cùng tác vụ và giữ nguyên bản nháp đã duyệt.

### 08. Standup · Lỗi chưa xác định

1. Dùng ghi chú mẫu, xác nhận lịch và bấm **Chạy mô phỏng**.
2. Chờ **Nộp thất bại** với thông báo “Không xác định được kết quả nộp trong mô phỏng.”
3. Bấm **Thử lại** một lần. Mở **Tác vụ** để kiểm tra trạng thái cuối.

**Dấu hiệu đạt** — Agent hiển thị lỗi và chờ người dùng quyết định. Sau khi thử lại, danh sách vẫn có cùng một tác vụ Standup, nay ở trạng thái **Nộp thành công**.

## Outlook

Sau khi bắt đầu kịch bản, đợi thông báo **Đang kiểm tra Outlook…** chuyển thành kết quả, yêu cầu kết nối hoặc thông báo lỗi.

### 09. Outlook · Thành công

1. Xem phạm vi mặc định **24 giờ gần nhất** và các số trên thẻ **Tổng hợp Outlook**.
2. Ở thư **Cập nhật hạn gửi tài liệu Sprint Review**, bấm **Xem chuỗi thư (2)**. Mở một **email gốc** để đối chiếu nội dung mô phỏng rồi đóng cửa sổ.
3. Trong bảng **Deadline và lịch hẹn**, bấm **Đặt nhắc** cạnh **Họp đồng bộ dự án**. Chọn giờ trước cuộc họp, bấm **Xác nhận lịch** rồi kiểm tra trong **Tác vụ**.
4. Đánh dấu một mục trong **Việc cần làm**. Bấm **Phạm vi Outlook**, chọn **3 ngày gần nhất** và **Cần phản hồi**, rồi bấm **Kiểm tra Outlook** để minh họa lọc trong cùng cuộc trò chuyện.

**Dấu hiệu đạt** — Phạm vi mặc định có 6 email đã phân tích, 3 email quan trọng, 3 việc cần làm và 2 deadline hoặc lịch hẹn. Bảng chỉ dùng hạn Sprint Review từ thư cập nhật mới nhất. Lời nhắc xuất hiện sau khi xác nhận và công việc đã làm có dấu tích.

### 10. Outlook · Phiên hết hạn

1. Khi chat báo phiên Outlook hết hạn, mở **Phạm vi Outlook**, chọn **3 ngày gần nhất** và bấm **Kiểm tra Outlook**.
2. Bấm **Kết nối Microsoft** trên yêu cầu kết nối mới nhất.
3. Bấm **Cấp quyền đọc** trong cửa sổ mô phỏng. Quay lại chat và đợi kết quả.

**Dấu hiệu đạt** — Sau khi kết nối, agent tự tiếp tục trong cùng cuộc trò chuyện. Thẻ tổng hợp ghi **3 ngày gần nhất**, là phạm vi đã chọn trước khi xác thực.

### 11. Outlook · Không có email mới

1. Chờ kết quả mặc định. Chỉ vào số email đã phân tích và thông báo bên dưới.
2. Có thể bấm **Đổi phạm vi**, chọn **7 ngày gần nhất** rồi kiểm tra lại.

**Dấu hiệu đạt** — Có 0 email đã phân tích và thông báo **Không có email trong phạm vi đã chọn**. Giao diện xác nhận Outlook đã được kiểm tra thành công.

### 12. Outlook · Không có email quan trọng

1. Chờ kết quả trong **24 giờ gần nhất**.
2. Chỉ vào số email đã phân tích, số email quan trọng và phần giải thích.

**Dấu hiệu đạt** — Có 2 email đã phân tích và 0 email quan trọng. Giao diện ghi **Không có email quan trọng** và giải thích rằng lượt kiểm tra có thư mới.

### 13. Outlook · Thiếu hạn và mâu thuẫn

1. Tìm mục **Xác nhận đã mở được file thiết kế** trong **Việc cần làm**. Chỉ vào dòng **Email chưa nêu thời hạn**.
2. Tìm cảnh báo **Giờ hẹn chưa được xác nhận** của **Demo bàn giao**. Bấm **Xem chuỗi thư** và đối chiếu hai giờ 09:30 và 14:00.
3. Kiểm tra phần tổng hợp deadline và lịch hẹn. Agent vẫn ghi lại việc cần xác nhận giờ với người tổ chức.

**Dấu hiệu đạt** — Công việc Figma vẫn xuất hiện với hạn để trống. Cả hai giờ hẹn được giữ trong cảnh báo và không có lịch đã xác nhận để đặt nhắc.

### 14. Outlook · Phân tích một phần

1. Chờ thẻ **Tổng hợp Outlook** rồi xem cảnh báo **Chỉ phân tích được một phần**.
2. Chỉ vào hai mục bị bỏ qua. **File bàn giao tuần này** có tệp được bảo vệ. **Cập nhật từ nhóm vận hành** gặp lỗi truy xuất nội dung email.
3. Kéo xuống **Email cần chú ý**, **Deadline và lịch hẹn** hoặc **Việc cần làm** để xem kết quả từ các thư đã đọc được.

**Dấu hiệu đạt** — Giao diện nêu từng giới hạn cụ thể và vẫn hiển thị kết quả phân tích của 6 email đọc được.

### 15. Outlook · Lỗi truy xuất

1. Đợi lượt đọc đầu tiên báo lỗi mạng. Chỉ vào dòng “Chưa xác định được có email quan trọng hay không.”
2. Bấm **Thử lại** ngay trong chat.
3. Kiểm tra thẻ **Tổng hợp Outlook** và phạm vi của lần đọc lại.

**Dấu hiệu đạt** — Lượt đầu hiển thị lỗi truy xuất. Lượt sau trả kết quả trong cùng phạm vi và cùng cuộc trò chuyện.

## Thao tác bổ sung

- **Đính kèm ghi chú** — Trong chat Standup, bấm **Đính kèm tài liệu** và chọn tệp TXT, Markdown, CSV hoặc JSON có hai dòng bắt đầu bằng `Hôm qua:` và `Ngày mai:`. Bấm **Gửi yêu cầu** để đưa nội dung vào bản nháp. PDF, DOCX, tệp quá lớn và nội dung không đọc được sẽ hiện phản hồi để người dùng bổ sung bằng ghi chú.
- **Hủy Standup** — Trong thẻ tác vụ, bấm **Hủy → Hủy tác vụ** rồi kiểm tra **Tác vụ → Đã hủy**. Nếu đang xem bản nháp, bấm **Tự nộp thủ công** để sao chép nội dung rồi bấm **Chọn tự nộp** để hủy tác vụ tự động. Trong buổi demo, dừng ở bước xác nhận trong Digitalboo.
- **Thử yêu cầu chưa rõ hoặc ngoài phạm vi** — Tạo **Cuộc trò chuyện mới**, gửi `Tôi muốn kiểm tra` để agent hỏi lại. Gửi `Cho tôi xem dự báo thời tiết` để thấy agent giới thiệu hai tính năng có thể hỗ trợ.

## Mã nguồn

- `mock.mjs` quản lý kịch bản, dữ liệu Outlook, lọc thư và kết quả tác vụ.
- `app.mjs` điều phối hội thoại, tác vụ, phiên đăng nhập, thông báo và lưu dữ liệu cục bộ.
- `views.mjs` dựng giao diện và các thẻ tương tác dùng lại ở nhiều màn hình.
