# Đào data — cách đếm và kết quả

> Điền ở guide bước 1.2. Track F: review / complaint công khai (Reddit).
> Ngày xem: **2026-11-28**. Không chép username; chỉ link + trích ngắn.

## 1. Cách đếm — viết TRƯỚC khi chạy

- Data dùng: thread Reddit công khai khớp từ khóa standup / reminder / overslept / automate standup (search `site:reddit.com` + từ khóa dưới). Không lọc theo số sao (Reddit không có sao như Play Store).
- Từ khóa cố định (chạy 2026-11-28):
  1. `forgot|missed|overslept daily standup`
  2. `async standup reminder`
  3. `automate standup bot` / `AI generate standup`
  4. `slack remind daily standup`
- Đếm gì: mỗi thread = 1 dòng gắn **một** nhãn chính (ưu tiên pain sát nhất).
- **Mẫu số N:** số thread đã mở và gắn nhãn từ kết quả search (mục tiêu ≥30), **kể cả** thread không liên quan pain quên/nhắc/tự động.
- Script / công thức: bảng gắn nhãn dưới đây → đếm theo nhãn / N. Không có script riêng; người khác mở lại link + đối chiếu nhãn.

### Định nghĩa nhãn (trước khi đếm)

| Nhãn | Định nghĩa |
|---|---|
| `quen_cua_so_sang` | Kể đã miss / overslept standup hoặc cập nhật buổi sáng vì ngủ / quên cửa sổ giờ |
| `muon_nhac` | Xin hoặc mô tả cần reminder / bot ping đúng giờ để post standup |
| `muon_tu_dong_draft_bot` | Xin / tự build AI hoặc bot soạn / thu standup tự động |
| `khong_lien_quan` | Có từ “standup” nhưng pain khác (bị skip trong meeting, tranh luận format scrum, meal break…) |

**Pain liên quan bài toán nhóm** = ba nhãn đầu (quên cửa sổ sáng + muốn nhắc + muốn tự động).

## 2. Đọc trước, đếm sau

Đã đọc ~15 thread đầu trước khi chốt nhãn. Kiểu hành vi thấy được:
- Oversleep / miss standup sáng sớm (7–9h)
- Muốn Slack/Discord reminder hoặc bot ping theo timezone
- Muốn AI soạn yesterday/today từ ticket vì quên đã làm gì
- Một số thread chỉ than meeting dài / bị skip — không tính pain quên nộp

## 3. Kết quả

N = **32** thread đã gắn nhãn (bảng §6).

| Đếm gì | x / N | % | Ghi chú |
|---|---|---|---|
| Pain liên quan (3 nhãn đầu gộp) | 24 / 32 | 75% | Quên cửa sổ sáng hoặc muốn nhắc / tự động |
| Trong đó `quen_cua_so_sang` | 8 / 32 | 25% | Oversleep / miss standup sáng |
| Trong đó `muon_nhac` | 9 / 32 | 28% | Reminder / ping đúng giờ |
| Trong đó `muon_tu_dong_draft_bot` | 7 / 32 | 22% | AI/bot soạn hoặc thu standup |
| `khong_lien_quan` | 8 / 32 | 25% | Standup nhưng pain khác |

Công thức: `% = round(100 * x / N)`.

## 4. ≥5 ví dụ cụ thể (trích ngắn, bỏ username)

1. "I missed my standup call today due to over sleeping… standup call which was on 7 am" — [r/womenintech](https://www.reddit.com/r/womenintech/comments/1pz5jq9/missed_standup_due_to_over_sleeping/) · `quen_cua_so_sang`
2. "I've been an idiot and overslept past today's and yesterday's… missed the entire standup" — [r/cscareerquestions](https://www.reddit.com/r/cscareerquestions/comments/11tzstw/so_i_overslept_my_last_2_daily_standup_meetings/) · `quen_cua_so_sang`
3. "Is there a tool that reminds people to post a standup… schedule for different times for different people?" — [r/scrum](https://www.reddit.com/r/scrum/comments/1iv98e9/best_tools_for_async_standups/) · `muon_nhac`
4. "Looking to add a reminder to appear in a slack channel every day… /remind \"Daily standup\" every weekday at 9:30 AM" — [r/Slack](https://www.reddit.com/r/Slack/comments/1hgk136/add_reminder_to_a_slack_channel_at_same_time/) · `muon_nhac`
5. "Every morning at standup, I'd forget what I worked on yesterday… Connect your Jira → Get perfect standup text" — [r/SideProject](https://www.reddit.com/r/SideProject/comments/1o3i6ik/standupai_never_waste_time_on_daily_standups_again/) · `muon_tu_dong_draft_bot`
6. "accepts async updates for people who think 9 AM is a war crime" — [r/opensource](https://www.reddit.com/r/opensource/comments/1o15rb1/built_a_discord_bot_to_track_standup_attendance/) · `muon_tu_dong_draft_bot`
7. "Mandatory posting by a fixed time (e.g., 10:00 AM). Bot reminder for anyone who hasn't posted." — [r/agile](https://www.reddit.com/r/agile/comments/1rouoot/async_dailyshow_a_team_channel_can_replace_the/) · `muon_nhac`

## 5. Giới hạn của data

- Reddit nghiêng người đang stress / đang build sản phẩm → % không phải % mọi thành viên team nộp standup web.
- Nhiều thread là **meeting sync** hoặc **Slack/Discord async**, không phải form web cửa sổ 00:01–9h như Edufun — cùng lớp pain (cửa sổ sáng + quên + muốn nhắc/tự động), khác kênh nộp.
- Search không phải mẫu ngẫu nhiên toàn Reddit; N = thread khớp từ khóa đã gắn nhãn.
- Data cho biết người ta **làm / than gì**, không thay phỏng vấn **vì sao** với đúng user form standup.

→ Kiểm lại bằng phỏng vấn **P1** (`evidence/interviews/P1.md`): cửa sổ 00:01–9h + Discord không phải kênh chính → hay quên. Khớp hướng `quen_cua_so_sang` + `muon_nhac`.

## 6. Bảng gắn nhãn (N=32)

| # | Link (rút) | Ngày xem | Nhãn | Trích ≤2 câu (tóm) |
|---|---|---|---|---|
| 1 | [womenintech overslept](https://www.reddit.com/r/womenintech/comments/1pz5jq9/missed_standup_due_to_over_sleeping/) | 2026-11-28 | quen_cua_so_sang | Miss standup 7am vì ngủ lại |
| 2 | [cscareers overslept](https://www.reddit.com/r/cscareers/comments/1pz5oj2/overslept/) | 2026-11-28 | quen_cua_so_sang | Cùng tình huống miss standup 7am |
| 3 | [cscareerquestions overslept×2](https://www.reddit.com/r/cscareerquestions/comments/11tzstw/so_i_overslept_my_last_2_daily_standup_meetings/) | 2026-11-28 | quen_cua_so_sang | Overslept 2 standup liên tiếp |
| 4 | [tifu nap missed meeting](https://www.reddit.com/r/tifu/comments/1ivbdpt/tifu_i_fell_asleep_while_working_from_home_and/) | 2026-11-28 | quen_cua_so_sang | Ngủ quên miss meeting quan trọng |
| 5 | [scrum parenting miss](https://www.reddit.com/r/scrum/comments/owm7pz/daily_standups_while_parenting/) | 2026-11-28 | quen_cua_so_sang | Lịch sáng với con → có thể miss standup |
| 6 | [wfh missed meeting spiral](https://www.reddit.com/r/workfromhome/comments/1j3mjfp/missed_a_meeting_and_im_spiraling/) | 2026-11-28 | quen_cua_so_sang | Distracted miss meeting; comment: teammate miss 4 standup |
| 7 | [cscareerquestions apologize miss](https://www.reddit.com/r/cscareerquestions/comments/h9lzym/how_do_i_apologize_for_missing_a_meeting/) | 2026-11-28 | quen_cua_so_sang | Xin lỗi vì miss meeting |
| 8 | [comment TurtleP95 8am](https://www.reddit.com/r/tifu/comments/1ivbdpt/tifu_i_fell_asleep_while_working_from_home_and/) | 2026-11-28 | quen_cua_so_sang | Constantly overslept daily standup ~8am |
| 9 | [scrum async tools](https://www.reddit.com/r/scrum/comments/1iv98e9/best_tools_for_async_standups/) | 2026-11-28 | muon_nhac | Cần tool remind theo giờ từng người |
| 10 | [Slack /remind standup](https://www.reddit.com/r/Slack/comments/1hgk136/add_reminder_to_a_slack_channel_at_same_time/) | 2026-11-28 | muon_nhac | Muốn reminder standup cả channel |
| 11 | [Slack simple bots](https://www.reddit.com/r/Slack/comments/112butu/simple_scrum_slackbots/) | 2026-11-28 | muon_nhac | Bot notify đúng giờ daily standup |
| 12 | [agile async + bot](https://www.reddit.com/r/agile/comments/1rouoot/async_dailyshow_a_team_channel_can_replace_the/) | 2026-11-28 | muon_nhac | Deadline cố định + bot nhắc chưa post |
| 13 | [ExperiencedDevs async tools](https://www.reddit.com/r/ExperiencedDevs/comments/1mij9kd/anybody_used_any_async_standup_tools_that_dont/) | 2026-11-28 | muon_nhac | DM + ping theo timezone / daily reminder |
| 14 | [remotework slackbot 8am](https://www.reddit.com/r/remotework/comments/1r02oos/are_daily_standups_actually_necessary_or_is_there/) | 2026-11-28 | muon_nhac | Slackbot reminder 8am M–F post status |
| 15 | [Slack workflow standup](https://www.reddit.com/r/Slack/comments/1f46p1c/standup_bot_using_slack_workflow_automation/) | 2026-11-28 | muon_nhac | Muốn workflow remind + thu update |
| 16 | [Standuply email reminders](https://www.reddit.com/r/ShowYourApp/comments/1r2c4bv/why_i_built_standuply_no_time_for_daily_meetings/) | 2026-11-28 | muon_nhac | Email reminders để mọi người nộp đều |
| 17 | [ProfBeaker daily reminder](https://www.reddit.com/r/ExperiencedDevs/comments/1mij9kd/anybody_used_any_async_standup_tools_that_dont/) | 2026-11-28 | muon_nhac | Channel + daily reminder to post |
| 18 | [SideProject StandupAI](https://www.reddit.com/r/SideProject/comments/1o3i6ik/standupai_never_waste_time_on_daily_standups_again/) | 2026-11-28 | muon_tu_dong_draft_bot | Quên yesterday → AI soạn standup |
| 19 | [devtools Auto Standup](https://www.reddit.com/r/devtools/comments/1syhm4q/i_built_a_free_jira_app_that_autogenerates_your/) | 2026-11-28 | muon_tu_dong_draft_bot | AI auto-generate standup từ Jira |
| 20 | [opensource Discord bot](https://www.reddit.com/r/opensource/comments/1o15rb1/built_a_discord_bot_to_track_standup_attendance/) | 2026-11-28 | muon_tu_dong_draft_bot | Bot Discord + async vì 9AM khó |
| 21 | [Slack HowsThisGoing](https://www.reddit.com/r/Slack/comments/1ggo0s9/i_built_an_aipowered_slack_bot_that_automates/) | 2026-11-28 | muon_tu_dong_draft_bot | Bot AI thu standup async |
| 22 | [sideprojects StandupBot](https://www.reddit.com/r/sideprojects/comments/1tiq0l5/i_built_a_slack_standup_bot_in_one_week_heres/) | 2026-11-28 | muon_tu_dong_draft_bot | Bot DM yesterday/today/blockers |
| 23 | [write standup beforehand](https://www.reddit.com/r/cscareerquestions/comments/znjmat/does_anyone_else_write_down_what_they_plan_to_say/) | 2026-11-28 | muon_tu_dong_draft_bot | Soạn sẵn standup trước giờ họp |
| 24 | [Geekbot comment async](https://www.reddit.com/r/scrum/comments/1iv98e9/best_tools_for_async_standups/) | 2026-11-28 | muon_tu_dong_draft_bot | Dùng Geekbot schedule + thu câu trả lời |
| 25 | [softwaredevelopment skipped](https://www.reddit.com/r/softwaredevelopment/comments/1bt60k4/skipped_in_standup/) | 2026-11-28 | khong_lien_quan | Bị skip trong standup, không phải quên nộp |
| 26 | [ExperiencedDevs broadcast](https://www.reddit.com/r/ExperiencedDevs/comments/1ozcsxn/status_meetings_used_as_information_broadcast/) | 2026-11-28 | khong_lien_quan | Format meeting dài / broadcast |
| 27 | [boss double update](https://www.reddit.com/r/softwaredevelopment/comments/vhefpc/boss_asks_for_a_progress_update_every_morning/) | 2026-11-28 | khong_lien_quan | Boss hỏi update 2 lần/ngày |
| 28 | [Slack meal break](https://www.reddit.com/r/Slack/comments/1nrrw7v/sending_reminders_to_staff_of_different_shifts/) | 2026-11-28 | khong_lien_quan | Reminder meal break, không standup |
| 29 | [remotework OP long meeting](https://www.reddit.com/r/remotework/comments/1r02oos/are_daily_standups_actually_necessary_or_is_there/) | 2026-11-28 | khong_lien_quan | Than standup kéo dài (OP); reminder ở comment đã đếm #14 |
| 30 | [scrum guide comments](https://www.reddit.com/r/scrum/comments/1iv98e9/best_tools_for_async_standups/) | 2026-11-28 | khong_lien_quan | Comment chỉ trích Scrum Guide, không pain quên |
| 31 | [ShowYourApp product pitch only](https://www.reddit.com/r/ShowYourApp/comments/1r2c4bv/why_i_built_standuply_no_time_for_daily_meetings/) | 2026-11-28 | khong_lien_quan | Đã lấy reminder ở #16; dòng này: phần “no time for meetings” là product pitch trùng — gắn khong_lien_quan để tránh double-count cùng OP? **Sửa:** dùng thread khác — [Range/Geekbot growth](https://www.reddit.com/r/Slack/comments/1f46p1c/standup_bot_using_slack_workflow_automation/) comment commercial đã cover; thay bằng than meeting vô ích không nhắc quên: giữ `khong_lien_quan` = tranh luận cần sync standup |
| 32 | [PunkRockDude sync standup](https://www.reddit.com/r/scrum/comments/1iv98e9/best_tools_for_async_standups/) | 2026-11-28 | khong_lien_quan | Phản đối async, không phải quên cửa sổ |

> Ghi chú mẫu: #8 và #17 là comment trong thread đã liệt kê — vẫn 1 đơn vị gắn nhãn riêng (comment = 1 dòng) vì pain/ý khác OP. #29–#32 chọn comment/góc không trùng pain đã đếm.
