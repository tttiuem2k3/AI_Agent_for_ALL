THÔNG TIN API ASOFT AI SERVICES VÀ HƯỚNG DẪN KIỂM THỬ BẰNG POSTMAN

Địa chỉ Server:
http://192.168.0.134:8000

Swagger UI:
http://192.168.0.134:8000/docs

OpenAPI JSON:
http://192.168.0.134:8000/openapi.json

Lưu ý:
Máy chạy Postman phải truy cập được địa chỉ 192.168.0.134.
Firewall Windows phải cho phép kết nối đến cổng 8000.
Backend phải chạy với host 0.0.0.0 để máy khác trong mạng LAN truy cập được.

================================================================================
TỔNG HỢP TÊN VÀ Ý NGHĨA TOÀN BỘ API
================================================================================

GET /agent/schema — Lấy cấu trúc cấu hình Agent.
GET /agent/ — Lấy danh sách Agent.
POST /agent/ — Tạo Agent mới.
PATCH /agent/{agent_id} — Cập nhật Agent.
DELETE /agent/{agent_id} — Xóa Agent và dữ liệu liên quan.

GET /credential/schemas — Lấy cấu trúc các loại Credential.
GET /credential/ — Lấy danh sách Credential.
POST /credential/ — Tạo Credential mới.
PATCH /credential/{credential_id} — Cập nhật Credential.
DELETE /credential/{credential_id} — Xóa Credential.

GET /model/ — Lấy danh sách mô hình LLM theo Provider.
GET /tts-model/ — Lấy danh sách mô hình Text-to-Speech.

GET /sessions/ — Lấy danh sách Session của Agent.
POST /sessions/ — Tạo Session mới.
PATCH /sessions/{session_id} — Cập nhật cấu hình Session.
DELETE /sessions/{session_id} — Xóa Session và lịch sử liên quan.
GET /sessions/{session_id}/messages — Lấy lịch sử Message của Session.
GET /sessions/{session_id}/stream — Nhận sự kiện Agent theo thời gian thực qua SSE.

POST /chat/ — Gửi Message, gửi kết quả xác nhận hoặc tiếp tục Chat Run.

GET /schedule/ — Lấy danh sách lịch chạy Agent.
POST /schedule/ — Tạo lịch chạy Agent.
PATCH /schedule/{schedule_id} — Cập nhật hoặc tạm dừng lịch chạy.
DELETE /schedule/{schedule_id} — Xóa lịch chạy và các Session liên quan.
GET /schedule/{schedule_id}/sessions — Lấy lịch sử Session do Schedule tạo.

GET /workspace/mcp — Lấy danh sách MCP của Workspace.
POST /workspace/mcp — Thêm MCP vào Workspace.
DELETE /workspace/mcp/{mcp_name} — Xóa MCP khỏi Workspace.

GET /workspace/skill — Lấy danh sách Skill của Workspace.
POST /workspace/skill — Thêm Skill vào Workspace.
DELETE /workspace/skill/{skill_name} — Xóa Skill khỏi Workspace.

GET /docs — Mở tài liệu Swagger UI.
GET /redoc — Mở tài liệu ReDoc.
GET /openapi.json — Lấy đặc tả OpenAPI của toàn bộ Service.

================================================================================
1. CẤU HÌNH POSTMAN
================================================================================

Tạo Postman Environment với các biến sau:

base_url = http://192.168.0.134:8000
user_id = postman-test-user
agent_id = để trống
credential_id = để trống
session_id = để trống
schedule_id = để trống
provider = để trống
model_name = để trống

Header chung cho các API có dữ liệu người dùng:

X-User-ID: {{user_id}}

Header bổ sung khi request có Body:

Content-Type: application/json

Web UI hiện cũng sử dụng đúng cơ chế này. Web UI đọc địa chỉ Server và tên
người dùng từ localStorage, sau đó gửi X-User-ID trong mỗi request.

================================================================================
2. THỨ TỰ KIỂM THỬ KHUYẾN NGHỊ
================================================================================

Bước 1: Xem Credential Schema.
Bước 2: Tạo Credential và lưu credential_id.
Bước 3: Liệt kê model của Provider.
Bước 4: Xem Agent Schema.
Bước 5: Tạo Agent và lưu agent_id.
Bước 6: Tạo Session và lưu session_id.
Bước 7: Mở kết nối SSE của Session.
Bước 8: Gửi Message đến Chat API.
Bước 9: Quan sát Text, Thinking và Tool Event trên SSE.
Bước 10: Đọc lịch sử Message.
Bước 11: Kiểm thử MCP và Skill.
Bước 12: Kiểm thử Schedule.
Bước 13: Xóa dữ liệu thử nghiệm.

================================================================================
3. CREDENTIAL API
================================================================================

--------------------------------------------------------------------------------
3.1. Lấy Schema của tất cả Credential
--------------------------------------------------------------------------------

Thông tin API:
Trả về JSON Schema của các loại Credential mà Server đang hỗ trợ. Nên gọi API
này trước khi tạo Credential để biết chính xác các trường cần truyền.

Method:
GET

API:
http://192.168.0.134:8000/credential/schemas

Header:
Không bắt buộc X-User-ID.

Body mẫu:
Không có Body.

Các loại Credential hiện có:
anthropic_credential
dashscope_credential
deepseek_credential
gemini_credential
moonshot_credential
ollama_credential
openai_credential
xai_credential

--------------------------------------------------------------------------------
3.2. Tạo Credential Ollama
--------------------------------------------------------------------------------

Thông tin API:
Tạo cấu hình kết nối đến Ollama Server.

Method:
POST

API:
http://192.168.0.134:8000/credential/

Header:
X-User-ID: {{user_id}}
Content-Type: application/json

Body mẫu:
{
  "data": {
    "type": "ollama_credential",
    "host": "http://localhost:11434"
  }
}

Giải thích từng trường:
data = Object chứa toàn bộ cấu hình Credential được lưu.
data.type = Loại Credential; Server dùng giá trị này để chọn Ollama Provider.
data.host = Địa chỉ Ollama API mà Python Backend sẽ kết nối.

Response mẫu:
{
  "credential_id": "ID_CREDENTIAL_DO_SERVER_TAO"
}

Postman Tests:
pm.test("Credential created", function () {
    pm.response.to.have.status(201);
});
pm.environment.set("credential_id", pm.response.json().credential_id);

Lưu ý:
localhost trong host là máy đang chạy Python Backend, không phải máy đang chạy
Postman. Nếu Ollama chạy ở máy khác, hãy thay bằng IP của máy Ollama.

--------------------------------------------------------------------------------
3.3. Tạo Credential OpenAI
--------------------------------------------------------------------------------

Thông tin API:
Lưu API key và thông tin kết nối OpenAI.

Method:
POST

API:
http://192.168.0.134:8000/credential/

Header:
X-User-ID: {{user_id}}
Content-Type: application/json

Body mẫu:
{
  "data": {
    "type": "openai_credential",
    "api_key": "YOUR_OPENAI_API_KEY",
    "organization": null,
    "base_url": null
  }
}

Giải thích từng trường:
data = Object chứa cấu hình Credential.
data.type = Chọn OpenAI Credential và OpenAI Model Adapter.
data.api_key = Khóa bí mật dùng để xác thực với OpenAI.
data.organization = ID Organization của OpenAI; có thể để null nếu không dùng.
data.base_url = Địa chỉ API tùy chỉnh; null nghĩa là dùng API OpenAI mặc định.

Body mẫu dành cho Server tương thích OpenAI:
{
  "data": {
    "type": "openai_credential",
    "api_key": "LOCAL_OR_PROVIDER_KEY",
    "organization": null,
    "base_url": "http://192.168.0.134:1234/v1"
  }
}

Giải thích từng trường:
data = Object chứa cấu hình kết nối.
data.type = Vẫn dùng OpenAI Adapter vì Server đích hỗ trợ giao thức OpenAI.
data.api_key = Khóa mà Server tương thích OpenAI yêu cầu.
data.organization = Organization ID; thường để null với Server cục bộ.
data.base_url = URL gốc có phiên bản API, thường kết thúc bằng /v1.

Lưu ý:
Không đưa API key thật vào Collection được commit lên Git.

--------------------------------------------------------------------------------
3.4. Liệt kê Credential của User
--------------------------------------------------------------------------------

Thông tin API:
Trả về các Credential thuộc X-User-ID hiện tại.

Method:
GET

API:
http://192.168.0.134:8000/credential/

Header:
X-User-ID: {{user_id}}

Body mẫu:
Không có Body.

Response mẫu:
{
  "credentials": [],
  "total": 0
}

--------------------------------------------------------------------------------
3.5. Cập nhật Credential
--------------------------------------------------------------------------------

Thông tin API:
Thay toàn bộ nội dung data của Credential. Đây không phải cập nhật riêng từng
trường nằm bên trong data.

Method:
PATCH

API:
http://192.168.0.134:8000/credential/{{credential_id}}

Header:
X-User-ID: {{user_id}}
Content-Type: application/json

Body mẫu:
{
  "data": {
    "type": "ollama_credential",
    "host": "http://127.0.0.1:11434"
  }
}

Giải thích từng trường:
data = Payload Credential mới sẽ thay thế payload cũ.
data.type = Loại Credential phải phù hợp với dữ liệu cập nhật.
data.host = Địa chỉ Ollama mới mà Backend sẽ sử dụng.

--------------------------------------------------------------------------------
3.6. Xóa Credential
--------------------------------------------------------------------------------

Thông tin API:
Xóa Credential theo ID.

Method:
DELETE

API:
http://192.168.0.134:8000/credential/{{credential_id}}

Header:
X-User-ID: {{user_id}}

Body mẫu:
Không có Body.

Response thành công:
HTTP 204 No Content.

================================================================================
4. MODEL API
================================================================================

--------------------------------------------------------------------------------
4.1. Liệt kê Chat Model theo Provider
--------------------------------------------------------------------------------

Thông tin API:
Trả về Model Catalog của loại Credential được truyền vào.

Method:
GET

API:
http://192.168.0.134:8000/model/?provider={{provider}}

Ví dụ:
http://192.168.0.134:8000/model/?provider=ollama_credential

Header:
Không bắt buộc X-User-ID.

Body mẫu:
Không có Body.

Lưu ý:
API đọc Model Catalog của Provider. Với Ollama, model sử dụng thực tế vẫn phải
được cài trên Ollama Server.

--------------------------------------------------------------------------------
4.2. Liệt kê TTS Model
--------------------------------------------------------------------------------

Thông tin API:
Trả về danh sách Text-to-Speech Model của Provider.

Method:
GET

API:
http://192.168.0.134:8000/tts-model/?provider=dashscope_credential

Header:
Không bắt buộc X-User-ID.

Body mẫu:
Không có Body.

Lưu ý:
Server trả HTTP 404 nếu Provider không tồn tại hoặc không hỗ trợ TTS.

================================================================================
5. AGENT API
================================================================================

--------------------------------------------------------------------------------
5.1. Lấy Agent Schema
--------------------------------------------------------------------------------

Thông tin API:
Trả về Schema của Identity, Context Config và ReAct Config. Web UI dùng các
Schema này để sinh form tạo và chỉnh sửa Agent.

Method:
GET

API:
http://192.168.0.134:8000/agent/schema

Header:
Không bắt buộc X-User-ID.

Body mẫu:
Không có Body.

--------------------------------------------------------------------------------
5.2. Tạo Agent tối giản
--------------------------------------------------------------------------------

Thông tin API:
Tạo một Agent mới cho User hiện tại.

Method:
POST

API:
http://192.168.0.134:8000/agent/

Header:
X-User-ID: {{user_id}}
Content-Type: application/json

Body mẫu:
{
  "name": "ASOFT Postman Assistant",
  "system_prompt": "Bạn là trợ lý AI tiếng Việt dùng để kiểm thử API cho ERPX."
}

Giải thích từng trường:
name = Tên hiển thị của Agent trên Web UI và trong danh sách Agent.
system_prompt = Chỉ dẫn nền quy định vai trò, ngôn ngữ và hành vi của Agent.

Response mẫu:
{
  "agent_id": "ID_AGENT_DO_SERVER_TAO"
}

Postman Tests:
pm.test("Agent created", function () {
    pm.response.to.have.status(201);
});
pm.environment.set("agent_id", pm.response.json().agent_id);

--------------------------------------------------------------------------------
5.3. Tạo Agent đầy đủ
--------------------------------------------------------------------------------

Thông tin API:
Tạo Agent kèm cấu hình Context và vòng lặp ReAct.

Method:
POST

API:
http://192.168.0.134:8000/agent/

Header:
X-User-ID: {{user_id}}
Content-Type: application/json

Body mẫu:
{
  "name": "ASOFT ERPX Assistant",
  "system_prompt": "Bạn là trợ lý AI của ASOFT. Trả lời bằng tiếng Việt.",
  "context_config": {
    "trigger_ratio": 0.8,
    "reserve_ratio": 0.1,
    "tool_result_limit": 50000,
    "compression_prompt": "Hãy tóm tắt ngữ cảnh để tiếp tục công việc.",
    "summary_template": "{task_overview}\n{current_state}\n{next_steps}"
  },
  "react_config": {
    "max_iters": 20,
    "stop_on_reject": false
  }
}

Giải thích từng trường:
name = Tên hiển thị của Agent.
system_prompt = Chỉ dẫn hệ thống được gửi cho Model để xác định vai trò Agent.
context_config = Nhóm cấu hình quản lý và nén cửa sổ ngữ cảnh.
context_config.trigger_ratio = Tỷ lệ sử dụng Context Window bắt đầu kích hoạt
nén lịch sử.
context_config.reserve_ratio = Tỷ lệ Context được giữ lại khi thực hiện nén.
context_config.tool_result_limit = Giới hạn độ dài Tool Result trước khi bị
cắt bớt.
context_config.compression_prompt = Chỉ dẫn cho Model khi tạo bản tóm tắt lịch
sử cũ.
context_config.summary_template = Mẫu ghép các trường của bản tóm tắt thành
Context mới.
react_config = Nhóm cấu hình vòng lặp Reasoning và Acting.
react_config.max_iters = Số vòng gọi Model và Tool tối đa cho một Reply.
react_config.stop_on_reject = true thì dừng Reply khi Tool bị từ chối; false
thì Model có thể tiếp tục tìm phương án khác.

Lưu ý:
trigger_ratio phải lớn hơn 0 và nhỏ hơn 0.9.
reserve_ratio phải lớn hơn 0 và nhỏ hơn 0.9.
max_iters là số vòng reasoning và gọi Tool tối đa trong một câu trả lời.

--------------------------------------------------------------------------------
5.4. Liệt kê Agent
--------------------------------------------------------------------------------

Thông tin API:
Trả về tất cả Agent thuộc User hiện tại.

Method:
GET

API:
http://192.168.0.134:8000/agent/

Header:
X-User-ID: {{user_id}}

Body mẫu:
Không có Body.

--------------------------------------------------------------------------------
5.5. Cập nhật Agent
--------------------------------------------------------------------------------

Thông tin API:
Cập nhật một phần Agent. Trường không gửi lên được giữ nguyên.

Method:
PATCH

API:
http://192.168.0.134:8000/agent/{{agent_id}}

Header:
X-User-ID: {{user_id}}
Content-Type: application/json

Body mẫu:
{
  "name": "ASOFT Assistant đã cập nhật",
  "react_config": {
    "max_iters": 10,
    "stop_on_reject": true
  }
}

Giải thích từng trường:
name = Tên hiển thị mới của Agent.
react_config = Object thay thế cấu hình ReAct hiện tại.
react_config.max_iters = Số vòng Model và Tool tối đa sau khi cập nhật.
react_config.stop_on_reject = Quy định có dừng Agent ngay khi Tool bị từ chối
hay không.

--------------------------------------------------------------------------------
5.6. Xóa Agent
--------------------------------------------------------------------------------

Thông tin API:
Xóa Agent và các Session liên quan. Server cũng hủy Chat Run đang chạy và dọn
trạng thái Message Bus liên quan.

Method:
DELETE

API:
http://192.168.0.134:8000/agent/{{agent_id}}

Header:
X-User-ID: {{user_id}}

Body mẫu:
Không có Body.

Response thành công:
HTTP 204 No Content.

================================================================================
6. SESSION API
================================================================================

--------------------------------------------------------------------------------
6.1. Tạo Session có Model
--------------------------------------------------------------------------------

Thông tin API:
Tạo Session cho Agent và gắn Model dùng để Chat.

Method:
POST

API:
http://192.168.0.134:8000/sessions/

Header:
X-User-ID: {{user_id}}
Content-Type: application/json

Body mẫu:
{
  "agent_id": "{{agent_id}}",
  "name": "Phiên kiểm thử Postman",
  "workspace_id": "postman-workspace",
  "chat_model_config": {
    "type": "ollama_credential",
    "credential_id": "{{credential_id}}",
    "model": "{{model_name}}",
    "parameters": {}
  },
  "fallback_chat_model_config": null,
  "tts_model_config": null
}

Giải thích từng trường:
agent_id = ID Agent sở hữu Session.
name = Tên Session hiển thị trên Web UI.
workspace_id = ID vùng làm việc chứa file, Skill và MCP của Session.
chat_model_config = Cấu hình Model chính dùng để tạo câu trả lời.
chat_model_config.type = Loại Provider/Credential dùng để tạo Model Adapter.
chat_model_config.credential_id = ID Credential chứa API key hoặc thông tin
kết nối của Provider.
chat_model_config.model = Tên hoặc ID Model cần gọi.
chat_model_config.parameters = Tham số bổ sung truyền cho Model, ví dụ
temperature; object rỗng nghĩa là dùng mặc định.
fallback_chat_model_config = Model dự phòng khi Model chính thất bại; null
nghĩa là không dùng Model dự phòng.
tts_model_config = Cấu hình chuyển văn bản thành giọng nói; null nghĩa là tắt
TTS.

Response mẫu:
{
  "session_id": "ID_SESSION_DO_SERVER_TAO"
}

Postman Tests:
pm.test("Session created", function () {
    pm.response.to.have.status(201);
});
pm.environment.set("session_id", pm.response.json().session_id);

Lưu ý:
type phải trùng với type của Credential.
credential_id phải thuộc cùng X-User-ID.
model phải tồn tại trên Provider hoặc Ollama Server.
workspace_id và name có thể bỏ qua.

--------------------------------------------------------------------------------
6.2. Tạo Session chưa có Model
--------------------------------------------------------------------------------

Thông tin API:
Tạo Session trước và cấu hình Model sau bằng API cập nhật Session.

Method:
POST

API:
http://192.168.0.134:8000/sessions/

Header:
X-User-ID: {{user_id}}
Content-Type: application/json

Body mẫu:
{
  "agent_id": "{{agent_id}}",
  "name": "Cấu hình Model sau"
}

Giải thích từng trường:
agent_id = ID Agent sở hữu Session.
name = Tên Session hiển thị cho người dùng.

Lưu ý:
Session chưa thể Chat cho đến khi chat_model_config được cập nhật.

--------------------------------------------------------------------------------
6.3. Liệt kê Session theo Agent
--------------------------------------------------------------------------------

Thông tin API:
Trả về Session Record, trạng thái đang chạy và thông tin Team của mỗi Session.

Method:
GET

API:
http://192.168.0.134:8000/sessions/?agent_id={{agent_id}}

Header:
X-User-ID: {{user_id}}

Body mẫu:
Không có Body.

--------------------------------------------------------------------------------
6.4. Cập nhật tên và Permission của Session
--------------------------------------------------------------------------------

Thông tin API:
Cập nhật một phần cấu hình Session.

Method:
PATCH

API:
http://192.168.0.134:8000/sessions/{{session_id}}?agent_id={{agent_id}}

Header:
X-User-ID: {{user_id}}
Content-Type: application/json

Body mẫu:
{
  "name": "Phiên Postman đã đổi tên",
  "permission_mode": "accept_edits"
}

Giải thích từng trường:
name = Tên hiển thị mới của Session.
permission_mode = Chế độ quyết định Tool nào được tự chạy, bị từ chối hoặc cần
người dùng xác nhận.

Các giá trị permission_mode:
default = Hỏi xác nhận khi chưa có Rule cho phép.
accept_edits = Tự cho phép đọc và sửa trong Working Directory.
explore = Chỉ đọc, từ chối sửa đổi.
bypass = Bỏ qua phần lớn kiểm tra, chỉ dùng trong Sandbox tin cậy.
dont_ask = Chuyển yêu cầu xác nhận thành từ chối.

--------------------------------------------------------------------------------
6.5. Thay Chat Model của Session
--------------------------------------------------------------------------------

Thông tin API:
Thay toàn bộ Chat Model Config hiện tại.

Method:
PATCH

API:
http://192.168.0.134:8000/sessions/{{session_id}}?agent_id={{agent_id}}

Header:
X-User-ID: {{user_id}}
Content-Type: application/json

Body mẫu:
{
  "chat_model_config": {
    "type": "ollama_credential",
    "credential_id": "{{credential_id}}",
    "model": "qwen3:14b",
    "parameters": {
      "temperature": 0.2
    }
  }
}

Giải thích từng trường:
chat_model_config = Object Model chính mới, thay thế toàn bộ cấu hình cũ.
chat_model_config.type = Loại Provider và Credential.
chat_model_config.credential_id = ID Credential được dùng để xác thực.
chat_model_config.model = Tên Model mới.
chat_model_config.parameters = Tham số gọi Model.
chat_model_config.parameters.temperature = Mức độ ngẫu nhiên của câu trả lời;
giá trị thấp thường cho kết quả ổn định hơn.

--------------------------------------------------------------------------------
6.6. Tắt Fallback Model và TTS
--------------------------------------------------------------------------------

Method:
PATCH

API:
http://192.168.0.134:8000/sessions/{{session_id}}?agent_id={{agent_id}}

Header:
X-User-ID: {{user_id}}
Content-Type: application/json

Body mẫu:
{
  "fallback_chat_model_config": null,
  "tts_model_config": null
}

Giải thích từng trường:
fallback_chat_model_config = null để xóa Model dự phòng hiện tại.
tts_model_config = null để tắt chức năng Text-to-Speech của Session.

--------------------------------------------------------------------------------
6.7. Đọc lịch sử Message
--------------------------------------------------------------------------------

Thông tin API:
Trả về Message đã lưu theo thứ tự thời gian và trạng thái Chat Run.

Method:
GET

API:
http://192.168.0.134:8000/sessions/{{session_id}}/messages?agent_id={{agent_id}}&offset=0&limit=50

Header:
X-User-ID: {{user_id}}

Body mẫu:
Không có Body.

Response mẫu:
{
  "messages": [],
  "is_running": false
}

Giới hạn:
offset phải lớn hơn hoặc bằng 0.
limit phải từ 1 đến 200.

--------------------------------------------------------------------------------
6.8. Xóa Session
--------------------------------------------------------------------------------

Thông tin API:
Xóa Session, Message và trạng thái liên quan.

Method:
DELETE

API:
http://192.168.0.134:8000/sessions/{{session_id}}?agent_id={{agent_id}}

Header:
X-User-ID: {{user_id}}

Body mẫu:
Không có Body.

Response thành công:
HTTP 204 No Content.

================================================================================
7. CHAT VÀ SSE API
================================================================================

--------------------------------------------------------------------------------
7.1. Mở kết nối SSE
--------------------------------------------------------------------------------

Thông tin API:
Mở kết nối dài để nhận Text, Thinking, Tool Call, Tool Result và các Event khác
trong thời gian thực.

Method:
GET

API:
http://192.168.0.134:8000/sessions/{{session_id}}/stream?agent_id={{agent_id}}

Header:
X-User-ID: {{user_id}}
Accept: text/event-stream

Body mẫu:
Không có Body.

Thứ tự sử dụng:
Mở SSE trước.
Giữ request SSE đang chạy.
Mở request Postman khác để gọi POST Chat.
Quan sát các dòng data được trả về trên SSE.

Event mẫu:
data: {"type":"REPLY_START","reply_id":"..."}

data: {"type":"TEXT_BLOCK_DELTA","reply_id":"...","block_id":"...","delta":"Xin"}

data: {"type":"REPLY_END","reply_id":"..."}

Dòng chỉ chứa dấu hai chấm là Heartbeat được Server gửi mỗi 30 giây. Đây không
phải lỗi.

Nếu Postman không hiển thị SSE ổn định, có thể dùng PowerShell:

curl.exe -N -H "X-User-ID: postman-test-user" -H "Accept: text/event-stream" "http://192.168.0.134:8000/sessions/SESSION_ID/stream?agent_id=AGENT_ID"

--------------------------------------------------------------------------------
7.2. Gửi Message dạng Text
--------------------------------------------------------------------------------

Thông tin API:
Kích hoạt Chat Run. API trả kết quả started ngay; nội dung trả lời được gửi qua
SSE chứ không nằm trong Response của API này.

Method:
POST

API:
http://192.168.0.134:8000/chat/

Header:
X-User-ID: {{user_id}}
Content-Type: application/json

Body mẫu:
{
  "agent_id": "{{agent_id}}",
  "session_id": "{{session_id}}",
  "input": {
    "name": "{{user_id}}",
    "role": "user",
    "content": [
      {
        "type": "text",
        "text": "Hãy giới thiệu ngắn gọn về ASOFT AI Services."
      }
    ],
    "metadata": {}
  }
}

Giải thích từng trường:
agent_id = ID Agent sẽ xử lý yêu cầu.
session_id = ID Session chứa Model Config, lịch sử hội thoại và Runtime State.
input = User Message được gửi vào Agent.
input.name = Tên người gửi Message.
input.role = Vai trò Message; yêu cầu từ Client phải dùng user.
input.content = Danh sách Content Block, cho phép kết hợp Text và Data.
input.content[].type = Loại Block; text biểu thị nội dung văn bản.
input.content[].text = Câu hỏi hoặc chỉ dẫn thực tế gửi cho Agent.
input.metadata = Metadata mở rộng do Client tự gắn; object rỗng nếu không dùng.

Response mẫu:
{
  "status": "started",
  "session_id": "ID_SESSION"
}

Lưu ý:
Nếu Session đang có Chat Run mà gửi thêm Message, Server có thể trả HTTP 409.

--------------------------------------------------------------------------------
7.3. Gửi nhiều Message trong một lần
--------------------------------------------------------------------------------

Method:
POST

API:
http://192.168.0.134:8000/chat/

Header:
X-User-ID: {{user_id}}
Content-Type: application/json

Body mẫu:
{
  "agent_id": "{{agent_id}}",
  "session_id": "{{session_id}}",
  "input": [
    {
      "name": "{{user_id}}",
      "role": "user",
      "content": [
        {
          "type": "text",
          "text": "Thông tin thứ nhất: khách hàng đang sử dụng ERPX."
        }
      ]
    },
    {
      "name": "{{user_id}}",
      "role": "user",
      "content": [
        {
          "type": "text",
          "text": "Dựa vào thông tin trên, hãy đề xuất một ứng dụng AI."
        }
      ]
    }
  ]
}

Giải thích từng trường:
agent_id = ID Agent nhận danh sách Message.
session_id = ID Session cần tiếp tục.
input = Mảng Message được xử lý theo đúng thứ tự phần tử.
input[].name = Tên người gửi của từng Message.
input[].role = Vai trò của từng Message.
input[].content = Danh sách Content Block của từng Message.
input[].content[].type = Loại Block.
input[].content[].text = Nội dung văn bản của Block.

--------------------------------------------------------------------------------
7.4. Gửi ảnh bằng URL
--------------------------------------------------------------------------------

Thông tin API:
Gửi Text Block và Data Block trong cùng User Message.

Method:
POST

API:
http://192.168.0.134:8000/chat/

Header:
X-User-ID: {{user_id}}
Content-Type: application/json

Body mẫu:
{
  "agent_id": "{{agent_id}}",
  "session_id": "{{session_id}}",
  "input": {
    "name": "{{user_id}}",
    "role": "user",
    "content": [
      {
        "type": "text",
        "text": "Hãy đọc và mô tả nội dung ảnh này."
      },
      {
        "type": "data",
        "name": "hoa-don.png",
        "source": {
          "type": "url",
          "url": "https://example.com/hoa-don.png",
          "media_type": "image/png"
        }
      }
    ]
  }
}

Giải thích từng trường:
agent_id = ID Agent xử lý ảnh.
session_id = ID Session dùng cho yêu cầu Multimodal.
input = User Message gồm câu lệnh và dữ liệu ảnh.
input.name = Tên người gửi.
input.role = Vai trò user.
input.content = Danh sách gồm Text Block và Data Block.
Text Block type = text để mô tả yêu cầu cần thực hiện với ảnh.
Text Block text = Câu lệnh dành cho Model.
Data Block type = data để biểu thị file hoặc dữ liệu nhị phân.
Data Block name = Tên file dùng để hiển thị và cung cấp ngữ cảnh.
Data Block source = Nguồn cung cấp nội dung file.
source.type = url nghĩa là dữ liệu được lấy từ một URL.
source.url = Địa chỉ ảnh mà Provider phải truy cập được.
source.media_type = MIME type giúp hệ thống và Model nhận biết loại dữ liệu.

Lưu ý:
URL phải được Model Provider truy cập được.
Khả năng hiểu ảnh phụ thuộc Model.
Chat API không tự động gọi OCR Provider.

--------------------------------------------------------------------------------
7.5. Gửi PDF hoặc File bằng Base64
--------------------------------------------------------------------------------

Thông tin API:
Hiện chưa có Multipart Upload API. File được truyền bằng URL hoặc chuỗi Base64
trong Data Block.

Method:
POST

API:
http://192.168.0.134:8000/chat/

Header:
X-User-ID: {{user_id}}
Content-Type: application/json

Body mẫu:
{
  "agent_id": "{{agent_id}}",
  "session_id": "{{session_id}}",
  "input": {
    "name": "{{user_id}}",
    "role": "user",
    "content": [
      {
        "type": "text",
        "text": "Hãy OCR tài liệu đính kèm."
      },
      {
        "type": "data",
        "name": "hoa-don.pdf",
        "source": {
          "type": "base64",
          "data": "JVBERi0xLjQK...",
          "media_type": "application/pdf"
        }
      }
    ]
  }
}

Giải thích từng trường:
agent_id = ID Agent xử lý tài liệu.
session_id = ID Session nhận tài liệu.
input = User Message Multimodal.
input.name = Tên người gửi.
input.role = Vai trò user.
input.content = Danh sách Text Block và Data Block.
Text Block text = Yêu cầu Agent thực hiện với tài liệu.
Data Block name = Tên file gốc.
Data Block source.type = base64 nghĩa là dữ liệu file nằm trực tiếp trong JSON.
Data Block source.data = Nội dung byte của file sau khi mã hóa Base64.
Data Block source.media_type = MIME type của file, ở đây là application/pdf.

Lưu ý:
Trường data chỉ chứa chuỗi Base64.
Không thêm tiền tố data:application/pdf;base64, vào trường data.

--------------------------------------------------------------------------------
7.6. Tiếp tục Agent từ State hiện tại
--------------------------------------------------------------------------------

Method:
POST

API:
http://192.168.0.134:8000/chat/

Header:
X-User-ID: {{user_id}}
Content-Type: application/json

Body mẫu:
{
  "agent_id": "{{agent_id}}",
  "session_id": "{{session_id}}",
  "input": null
}

Giải thích từng trường:
agent_id = ID Agent cần tiếp tục.
session_id = ID Session chứa State đang chờ.
input = null yêu cầu Agent tiếp tục từ Runtime State hiện tại mà không thêm
User Message mới.

--------------------------------------------------------------------------------
7.7. Xác nhận Tool Call
--------------------------------------------------------------------------------

Thông tin API:
Khi SSE trả Event REQUIRE_USER_CONFIRM, Client gửi kết quả xác nhận về Chat
API để Agent tiếp tục.

Method:
POST

API:
http://192.168.0.134:8000/chat/

Header:
X-User-ID: {{user_id}}
Content-Type: application/json

Body mẫu:
{
  "agent_id": "{{agent_id}}",
  "session_id": "{{session_id}}",
  "input": {
    "type": "USER_CONFIRM_RESULT",
    "reply_id": "REPLY_ID_FROM_SSE",
    "confirm_results": [
      {
        "confirmed": true,
        "tool_call": {
          "type": "tool_call",
          "id": "TOOL_CALL_ID_FROM_SSE",
          "name": "Read",
          "input": "{\"file_path\":\"README.md\"}",
          "state": "asking",
          "suggested_rules": []
        },
        "rules": null
      }
    ]
  }
}

Giải thích từng trường:
agent_id = ID Agent đang chờ kết quả xác nhận.
session_id = ID Session đang bị tạm dừng tại Tool Call.
input = Event kết quả xác nhận gửi lại cho Runtime.
input.type = USER_CONFIRM_RESULT để Backend phân biệt với User Message.
input.reply_id = ID Reply đang chứa Tool Call cần xác nhận.
input.confirm_results = Danh sách kết quả xác nhận cho các Tool Call.
confirmed = true để cho phép chạy Tool; false để từ chối.
tool_call = Bản sao Tool Call nhận từ Event REQUIRE_USER_CONFIRM.
tool_call.type = Loại Content Block tool_call.
tool_call.id = ID dùng để ghép Tool Call với kết quả xác nhận và Tool Result.
tool_call.name = Tên Tool mà Model yêu cầu chạy.
tool_call.input = Chuỗi JSON Argument mà Tool sẽ nhận.
tool_call.state = Trạng thái hiện tại; asking nghĩa là đang chờ xác nhận.
tool_call.suggested_rules = Các Permission Rule do Backend đề xuất.
rules = Permission Rule mà người dùng chấp nhận lưu; null nghĩa là chỉ xử lý
lần xác nhận hiện tại.

Lưu ý:
Nên sao chép nguyên object tool_call nhận từ SSE để tránh sai Schema.
Đổi confirmed thành false để từ chối Tool.

--------------------------------------------------------------------------------
7.8. Các Event SSE thường gặp
--------------------------------------------------------------------------------

REPLY_START:
Bắt đầu một câu trả lời.

REPLY_END:
Kết thúc câu trả lời.

MODEL_CALL_START:
Bắt đầu gọi Model.

MODEL_CALL_END:
Kết thúc gọi Model và có thể chứa Token Usage.

TEXT_BLOCK_START:
Bắt đầu Text Block.

TEXT_BLOCK_DELTA:
Một phần nội dung Text mới.

TEXT_BLOCK_END:
Kết thúc Text Block.

THINKING_BLOCK_START:
Bắt đầu Thinking Block.

THINKING_BLOCK_DELTA:
Một phần nội dung Thinking mới.

THINKING_BLOCK_END:
Kết thúc Thinking Block.

TOOL_CALL_START:
Model bắt đầu yêu cầu Tool.

TOOL_CALL_DELTA:
Một phần JSON Argument của Tool.

TOOL_CALL_END:
Kết thúc tạo Tool Call.

TOOL_RESULT_START:
Tool bắt đầu chạy.

TOOL_RESULT_TEXT_DELTA:
Một phần Text Result của Tool.

TOOL_RESULT_DATA_DELTA:
Một phần Data Result của Tool.

TOOL_RESULT_END:
Tool đã hoàn thành hoặc gặp lỗi.

REQUIRE_USER_CONFIRM:
Tool cần người dùng xác nhận.

REQUIRE_EXTERNAL_EXECUTION:
Yêu cầu hệ thống bên ngoài thực thi.

EXCEED_MAX_ITERS:
Agent vượt quá số vòng ReAct.

CUSTOM:
Event mở rộng như cập nhật State, Task hoặc Team.

================================================================================
8. WORKSPACE MCP API
================================================================================

--------------------------------------------------------------------------------
8.1. Liệt kê MCP của Session
--------------------------------------------------------------------------------

Thông tin API:
Trả về MCP Client, trạng thái kết nối và Tool List.

Method:
GET

API:
http://192.168.0.134:8000/workspace/mcp?agent_id={{agent_id}}&session_id={{session_id}}

Header:
X-User-ID: {{user_id}}

Body mẫu:
Không có Body.

--------------------------------------------------------------------------------
8.2. Thêm HTTP MCP
--------------------------------------------------------------------------------

Thông tin API:
Thêm MCP Server sử dụng SSE hoặc Streamable HTTP vào Workspace.

Method:
POST

API:
http://192.168.0.134:8000/workspace/mcp?agent_id={{agent_id}}&session_id={{session_id}}

Header:
X-User-ID: {{user_id}}
Content-Type: application/json

Body mẫu:
{
  "name": "erp_search",
  "is_stateful": false,
  "mcp_config": {
    "type": "http_mcp",
    "url": "http://192.168.0.134:9000/mcp",
    "headers": null,
    "timeout": 30
  },
  "enable_tools": null,
  "disable_tools": null,
  "execution_timeout": 60
}

Giải thích từng trường:
name = Tên duy nhất của MCP trong Workspace; tên này cũng tham gia tạo tên
Tool mà Model nhìn thấy.
is_stateful = false nghĩa là tạo kết nối HTTP tạm thời theo lần gọi thay vì
duy trì Session MCP lâu dài.
mcp_config = Cấu hình Transport của MCP Server.
mcp_config.type = http_mcp để chọn HTTP/SSE hoặc Streamable HTTP Transport.
mcp_config.url = Endpoint của MCP Server.
mcp_config.headers = Header bổ sung, ví dụ Authorization; null nếu không cần.
mcp_config.timeout = Thời gian tối đa chờ kết nối HTTP, tính bằng giây.
enable_tools = Danh sách chỉ những Tool được bật; null nghĩa là không giới hạn.
disable_tools = Danh sách Tool bị loại bỏ; null nghĩa là không loại bỏ.
execution_timeout = Thời gian tối đa cho một lần MCP Tool thực thi.

Response thành công:
HTTP 201 Created và không có JSON Body.

--------------------------------------------------------------------------------
8.3. Thêm STDIO MCP
--------------------------------------------------------------------------------

Thông tin API:
Khởi động MCP Server bằng Process trên máy chạy Python Backend.

Method:
POST

API:
http://192.168.0.134:8000/workspace/mcp?agent_id={{agent_id}}&session_id={{session_id}}

Header:
X-User-ID: {{user_id}}
Content-Type: application/json

Body mẫu:
{
  "name": "filesystem",
  "is_stateful": true,
  "mcp_config": {
    "type": "stdio_mcp",
    "command": "npx",
    "args": [
      "-y",
      "@modelcontextprotocol/server-filesystem",
      "E:\\Asoft\\ASOFT_AI_SERVICES"
    ],
    "env": null,
    "cwd": "E:\\Asoft\\ASOFT_AI_SERVICES",
    "encoding_error_handler": "replace"
  },
  "enable_tools": null,
  "disable_tools": null,
  "execution_timeout": 60
}

Giải thích từng trường:
name = Tên MCP duy nhất trong Workspace.
is_stateful = true để giữ Process và MCP Session trong suốt vòng đời sử dụng.
mcp_config = Cấu hình Process STDIO.
mcp_config.type = stdio_mcp để chọn giao tiếp qua stdin và stdout.
mcp_config.command = Chương trình Server sẽ chạy.
mcp_config.args = Danh sách tham số truyền cho command.
mcp_config.env = Biến môi trường truyền vào Process; null để kế thừa cấu hình
mặc định.
mcp_config.cwd = Working Directory của Process.
mcp_config.encoding_error_handler = Cách xử lý ký tự không giải mã được;
replace sẽ thay ký tự lỗi thay vì dừng Process.
enable_tools = Danh sách Tool được phép hiển thị; null để dùng tất cả.
disable_tools = Danh sách Tool cần ẩn; null nếu không ẩn.
execution_timeout = Thời gian chạy tối đa của một MCP Tool.

Quy tắc:
name chỉ được chứa chữ, số, dấu gạch dưới và dấu gạch ngang.
STDIO MCP bắt buộc is_stateful bằng true.
Command phải tồn tại trên máy chạy Backend.
Một Tool không được đồng thời nằm trong enable_tools và disable_tools.

--------------------------------------------------------------------------------
8.4. Xóa MCP
--------------------------------------------------------------------------------

Thông tin API:
Xóa MCP khỏi Workspace theo tên.

Method:
DELETE

API:
http://192.168.0.134:8000/workspace/mcp/filesystem?agent_id={{agent_id}}&session_id={{session_id}}

Header:
X-User-ID: {{user_id}}

Body mẫu:
Không có Body.

Response thành công:
HTTP 204 No Content.

================================================================================
9. WORKSPACE SKILL API
================================================================================

--------------------------------------------------------------------------------
9.1. Liệt kê Skill
--------------------------------------------------------------------------------

Thông tin API:
Trả về các Skill hiện có trong Workspace của Session.

Method:
GET

API:
http://192.168.0.134:8000/workspace/skill?agent_id={{agent_id}}&session_id={{session_id}}

Header:
X-User-ID: {{user_id}}

Body mẫu:
Không có Body.

--------------------------------------------------------------------------------
9.2. Thêm Skill
--------------------------------------------------------------------------------

Thông tin API:
Nạp Skill từ đường dẫn trên máy chạy Python Backend.

Method:
POST

API:
http://192.168.0.134:8000/workspace/skill?agent_id={{agent_id}}&session_id={{session_id}}

Header:
X-User-ID: {{user_id}}
Content-Type: application/json

Body mẫu:
{
  "skill_path": "E:\\Asoft\\ASOFT_AI_SERVICES\\service\\skills\\example"
}

Giải thích từng trường:
skill_path = Đường dẫn tuyệt đối hoặc đường dẫn hợp lệ đến thư mục Skill trên
máy chạy Python Backend.

Lưu ý:
skill_path là đường dẫn trên Server, không phải đường dẫn trên máy Postman nếu
Postman chạy ở máy khác.

--------------------------------------------------------------------------------
9.3. Xóa Skill
--------------------------------------------------------------------------------

Thông tin API:
Xóa Skill khỏi Workspace theo tên.

Method:
DELETE

API:
http://192.168.0.134:8000/workspace/skill/example?agent_id={{agent_id}}&session_id={{session_id}}

Header:
X-User-ID: {{user_id}}

Body mẫu:
Không có Body.

Response thành công:
HTTP 204 No Content.

================================================================================
10. SCHEDULE API
================================================================================

--------------------------------------------------------------------------------
10.1. Liệt kê Schedule
--------------------------------------------------------------------------------

Thông tin API:
Trả về tất cả Schedule của User hiện tại.

Method:
GET

API:
http://192.168.0.134:8000/schedule/

Header:
X-User-ID: {{user_id}}

Body mẫu:
Không có Body.

--------------------------------------------------------------------------------
10.2. Tạo Schedule
--------------------------------------------------------------------------------

Thông tin API:
Tạo một tác vụ Agent chạy theo Cron.

Method:
POST

API:
http://192.168.0.134:8000/schedule/

Header:
X-User-ID: {{user_id}}
Content-Type: application/json

Body mẫu:
{
  "name": "Kiểm tra ERPX mỗi 5 phút",
  "description": "Schedule tạo từ Postman",
  "cron_expression": "*/5 * * * *",
  "timezone": "Asia/Bangkok",
  "agent_id": "{{agent_id}}",
  "chat_model_config": {
    "type": "ollama_credential",
    "credential_id": "{{credential_id}}",
    "model": "{{model_name}}",
    "parameters": {}
  },
  "enabled": true,
  "stateful": false,
  "permission_mode": "dont_ask"
}

Giải thích từng trường:
name = Tên Schedule hiển thị cho người quản trị.
description = Nội dung mô tả mục đích của Schedule.
cron_expression = Biểu thức Cron 5 trường quy định thời điểm chạy.
timezone = Múi giờ IANA dùng để diễn giải Cron.
agent_id = ID Agent được chạy khi Schedule kích hoạt.
chat_model_config = Cấu hình Model dùng trong Execution Session.
chat_model_config.type = Loại Provider và Credential.
chat_model_config.credential_id = ID Credential dùng để xác thực Model.
chat_model_config.model = Tên Model được Schedule sử dụng.
chat_model_config.parameters = Tham số bổ sung của Model.
enabled = true để đăng ký Job ngay; false để chỉ lưu mà chưa chạy.
stateful = true để các lần chạy dùng chung Session Context; false để mỗi lần
chạy độc lập.
permission_mode = Chế độ Permission khi chạy không có người giám sát;
dont_ask sẽ từ chối thao tác cần xác nhận.

Response mẫu:
{
  "schedule_id": "ID_SCHEDULE_DO_SERVER_TAO"
}

Postman Tests:
pm.test("Schedule created", function () {
    pm.response.to.have.status(201);
});
pm.environment.set("schedule_id", pm.response.json().schedule_id);

Lưu ý:
cron_expression dùng Cron 5 trường.
Tác vụ không có người giám sát nên dùng permission_mode bằng dont_ask.

--------------------------------------------------------------------------------
10.3. Cập nhật Schedule
--------------------------------------------------------------------------------

Thông tin API:
Cập nhật một phần Schedule. Đổi Cron hoặc Timezone sẽ đăng ký lại Job.

Method:
PATCH

API:
http://192.168.0.134:8000/schedule/{{schedule_id}}

Header:
X-User-ID: {{user_id}}
Content-Type: application/json

Body mẫu:
{
  "name": "Schedule đã tạm dừng",
  "enabled": false
}

Giải thích từng trường:
name = Tên mới của Schedule.
enabled = false để gỡ Job khỏi Scheduler nhưng vẫn giữ Schedule Record; có thể
đổi lại true để kích hoạt.

--------------------------------------------------------------------------------
10.4. Liệt kê Session do Schedule tạo
--------------------------------------------------------------------------------

Thông tin API:
Trả về các Session đã được tạo trong những lần Schedule thực thi.

Method:
GET

API:
http://192.168.0.134:8000/schedule/{{schedule_id}}/sessions

Header:
X-User-ID: {{user_id}}

Body mẫu:
Không có Body.

--------------------------------------------------------------------------------
10.5. Xóa Schedule
--------------------------------------------------------------------------------

Thông tin API:
Xóa Schedule, hủy Job và dọn các Execution Session liên quan.

Method:
DELETE

API:
http://192.168.0.134:8000/schedule/{{schedule_id}}

Header:
X-User-ID: {{user_id}}

Body mẫu:
Không có Body.

Response thành công:
HTTP 204 No Content.

================================================================================
11. MÃ TRẠNG THÁI THƯỜNG GẶP
================================================================================

HTTP 200:
Request GET, PATCH hoặc Chat Trigger thành công.

HTTP 201:
Tạo Agent, Credential, Session, Schedule, MCP hoặc Skill thành công.

HTTP 204:
Xóa thành công và không có Response Body.

HTTP 404:
Resource, Provider, Agent, Session hoặc Credential không tồn tại hoặc không
thuộc X-User-ID hiện tại.

HTTP 409:
Session đã có Chat Run đang chạy.

HTTP 422:
Thiếu Header, Query Parameter, Body hoặc JSON không đúng Schema.

HTTP 500:
Redis, Model Provider, MCP hoặc Dependency Runtime xảy ra lỗi.

Khi gặp HTTP 422, kiểm tra:
Đã gửi X-User-ID chưa.
Đã gửi Content-Type application/json chưa.
Query có đúng agent_id và session_id chưa.
Credential type có đúng chưa.
Content Block type có đúng text hoặc data chưa.
Data Source type có đúng url hoặc base64 chưa.
MCP type có đúng http_mcp hoặc stdio_mcp chưa.
Permission Mode có đúng chữ thường chưa.
Event Type có đúng chữ hoa chưa.

================================================================================
12. KỊCH BẢN SMOKE TEST HOÀN CHỈNH
================================================================================

Bước 1:
Gọi GET /credential/schemas.

Bước 2:
Gọi POST /credential/ và lưu credential_id.

Bước 3:
Gọi GET /model/?provider=ollama_credential.

Bước 4:
Gọi POST /agent/ và lưu agent_id.

Bước 5:
Gọi POST /sessions/ và lưu session_id.

Bước 6:
Mở GET /sessions/{{session_id}}/stream?agent_id={{agent_id}}.

Bước 7:
Gọi POST /chat/ với một Text Message.

Bước 8:
Chờ SSE nhận REPLY_END.

Bước 9:
Gọi GET /sessions/{{session_id}}/messages.

Bước 10:
Cập nhật tên hoặc Permission của Session.

Bước 11:
Gọi GET /workspace/mcp và GET /workspace/skill.

Bước 12:
Tạo, tạm dừng, kiểm tra và xóa Schedule.

Bước 13:
Xóa Session, Agent và Credential thử nghiệm.

================================================================================
13. LƯU Ý VỀ API HIỆN TẠI
================================================================================

Python Service chưa có Health Check Endpoint riêng.

Node Backend trong Web UI Test có Health Endpoint nhưng không phải Business
API chính của AI Service.

Chưa có Multipart Upload API. File đi qua Data Block bằng URL hoặc Base64.

Chưa có OCR và STT Endpoint riêng. OCR và STT hiện là Provider Contract.

Gửi ảnh hoặc PDF đến Chat phụ thuộc khả năng Multimodal của Model đã chọn.

POST /chat/ chỉ kích hoạt Chat Run. Nội dung trả lời đi qua SSE.

SSE cần Header X-User-ID nên Web UI sử dụng Fetch Streaming thay vì native
EventSource.

Live Event hiện dùng InMemoryMessageBus. Khi Backend restart, Live Event và
Replay Event trong RAM sẽ mất.

Message và Session State đã lưu trong Redis db1 vẫn còn sau khi Backend
restart nếu Redis Data vẫn được giữ.

OpenAPI tại http://192.168.0.134:8000/openapi.json là nguồn kiểm tra chính xác
nếu Schema API thay đổi trong tương lai.

