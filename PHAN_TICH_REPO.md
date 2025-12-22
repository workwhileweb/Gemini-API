# PHÂN TÍCH VÀ HỆ THỐNG HÓA REPOSITORY GEMINI-API

## 1. TỔNG QUAN DỰ ÁN

### 1.1. Mục đích
**Gemini-API** là một Python wrapper bất đồng bộ (asynchronous) được reverse-engineer từ ứng dụng web [Google Gemini](https://gemini.google.com) (trước đây là Bard). Thư viện này cho phép truy cập các tính năng của Gemini thông qua Python mà không cần sử dụng API chính thức của Google.

### 1.2. Thông tin cơ bản
- **Tên package**: `gemini-webapi`
- **Ngôn ngữ**: Python 3.10+
- **License**: GNU Affero General Public License v3.0 (AGPL-3.0)
- **Tác giả**: UZQueen
- **Repository**: https://github.com/HanaokaYuzu/Gemini-API

### 1.3. Dependencies chính
- `httpx~=0.28.1`: HTTP client bất đồng bộ
- `loguru~=0.7.3`: Hệ thống logging
- `orjson~=3.11.1`: JSON parser nhanh
- `pydantic~=2.12.2`: Data validation và serialization
- `browser-cookie3` (optional): Tự động lấy cookies từ trình duyệt

---

## 2. KIẾN TRÚC HỆ THỐNG

### 2.1. Cấu trúc thư mục

```
Gemini-API/
├── src/
│   └── gemini_webapi/          # Package chính
│       ├── __init__.py         # Public API exports
│       ├── client.py           # GeminiClient và ChatSession
│       ├── constants.py        # Constants (endpoints, models, errors)
│       ├── exceptions.py       # Custom exceptions
│       ├── components/
│       │   └── gem_mixin.py    # Mixin cho quản lý Gems
│       ├── types/              # Data models
│       │   ├── candidate.py    # Candidate (reply candidate)
│       │   ├── gem.py          # Gem và GemJar
│       │   ├── grpc.py         # RPCData cho batch requests
│       │   ├── image.py        # Image, WebImage, GeneratedImage
│       │   └── modeloutput.py  # ModelOutput
│       └── utils/              # Utilities
│           ├── decorators.py   # @running decorator
│           ├── get_access_token.py
│           ├── load_browser_cookies.py
│           ├── logger.py
│           ├── parsing.py      # JSON parsing helpers
│           ├── rotate_1psidts.py
│           └── upload_file.py
├── tests/                      # Test files
├── assets/                     # Resources (images, PDFs)
├── pyproject.toml              # Project configuration
├── README.md                   # Documentation
└── LICENSE                     # AGPL-3.0 license
```

### 2.2. Kiến trúc phân lớp

```
┌─────────────────────────────────────────┐
│         Public API Layer                │
│  (GeminiClient, ChatSession, Types)     │
└─────────────────────────────────────────┘
                    │
┌─────────────────────────────────────────┐
│         Business Logic Layer            │
│  (GemMixin, Content Generation, Gems)    │
└─────────────────────────────────────────┘
                    │
┌─────────────────────────────────────────┐
│         HTTP/Network Layer              │
│  (httpx.AsyncClient, Request Handling)  │
└─────────────────────────────────────────┘
                    │
┌─────────────────────────────────────────┐
│         Utility Layer                   │
│  (Parsing, Cookies, File Upload)        │
└─────────────────────────────────────────┘
```

---

## 3. CÁC THÀNH PHẦN CHÍNH

### 3.1. GeminiClient (`client.py`)

**Mục đích**: Client chính để tương tác với Gemini API.

**Tính năng chính**:
- **Khởi tạo và quản lý kết nối**: Tự động lấy access token, quản lý cookies
- **Auto-refresh cookies**: Tự động làm mới `__Secure-1PSIDTS` trong background
- **Auto-close**: Tự động đóng kết nối sau thời gian không hoạt động
- **Generate content**: Tạo nội dung từ prompt
- **File upload**: Hỗ trợ upload file (PDF, images)
- **Model selection**: Chọn model (gemini-3.0-pro, gemini-2.5-pro, gemini-2.5-flash)
- **Gem support**: Hỗ trợ Gemini Gems (system prompts)

**Các phương thức quan trọng**:
```python
async def init(...)          # Khởi tạo client
async def generate_content(...)  # Tạo nội dung
def start_chat(...)          # Tạo chat session
async def close(...)         # Đóng client
async def start_auto_refresh(...)  # Background cookie refresh
```

**State management**:
- `_running`: Trạng thái client đang chạy
- `cookies`: Dictionary chứa cookies
- `access_token`: Token để authenticate requests
- `client`: httpx.AsyncClient instance
- `_gems`: Cache cho Gemini Gems

### 3.2. ChatSession (`client.py`)

**Mục đích**: Quản lý cuộc hội thoại đa lượt (multi-turn conversation).

**Tính năng**:
- Lưu trữ metadata: `[cid, rid, rcid]` (chat id, reply id, reply candidate id)
- Tự động cập nhật metadata sau mỗi response
- Hỗ trợ chọn candidate từ nhiều reply options
- Hỗ trợ model và gem riêng cho session

**Các phương thức**:
```python
async def send_message(...)  # Gửi tin nhắn trong session
def choose_candidate(...)     # Chọn candidate khác
```

### 3.3. ModelOutput (`types/modeloutput.py`)

**Mục đích**: Đại diện cho output từ Gemini.

**Cấu trúc**:
- `metadata`: `[cid, rid, rcid]` - metadata của conversation
- `candidates`: Danh sách các reply candidates
- `chosen`: Index của candidate được chọn (mặc định 0)

**Properties**:
- `text`: Text của candidate được chọn
- `thoughts`: Thought process (cho thinking models)
- `images`: Danh sách images (web + generated)
- `rcid`: Reply candidate ID

### 3.4. Candidate (`types/candidate.py`)

**Mục đích**: Đại diện cho một reply candidate trong response.

**Cấu trúc**:
- `rcid`: Reply candidate ID
- `text`: Text output
- `thoughts`: Model's thought process (optional)
- `web_images`: Images từ web
- `generated_images`: Images được AI generate

**Validation**: Tự động decode HTML entities trong text và thoughts.

### 3.5. Image Types (`types/image.py`)

**Các loại Image**:

1. **Image** (base class):
   - `url`, `title`, `alt`
   - `async save(...)`: Lưu image xuống disk

2. **WebImage** (extends Image):
   - Images được lấy từ web khi yêu cầu "send images"

3. **GeneratedImage** (extends Image):
   - Images được generate bởi ImageFX (Google's AI image generator)
   - Yêu cầu cookies để download
   - Hỗ trợ full-size download (`full_size=True`)

### 3.6. Gem System (`types/gem.py`, `components/gem_mixin.py`)

**Mục đích**: Quản lý Gemini Gems (system prompts tùy chỉnh).

**Gem**: Object đại diện cho một Gem
- `id`, `name`, `description`, `prompt`, `predefined`

**GemJar**: Container để quản lý nhiều Gems
- `get(id/name)`: Lấy gem theo ID hoặc name
- `filter(predefined, name)`: Lọc gems

**GemMixin**: Mixin class cung cấp methods cho GeminiClient
- `fetch_gems()`: Lấy danh sách gems từ server
- `create_gem()`: Tạo custom gem mới
- `update_gem()`: Cập nhật gem
- `delete_gem()`: Xóa gem

### 3.7. Constants (`constants.py`)

**Endpoint**: URLs cho các API endpoints
- `GOOGLE`, `INIT`, `GENERATE`, `ROTATE_COOKIES`, `UPLOAD`, `BATCH_EXEC`

**Model**: Enum các models có sẵn
- `UNSPECIFIED`, `G_3_0_PRO`, `G_2_5_PRO`, `G_2_5_FLASH`
- Mỗi model có `model_name`, `model_header` (HTTP headers), `advanced_only`

**ErrorCode**: Error codes từ server
- `USAGE_LIMIT_EXCEEDED`, `MODEL_INCONSISTENT`, `IP_TEMPORARILY_BLOCKED`, etc.

**Headers**: HTTP headers cho các loại requests

**GRPC**: Google RPC IDs cho batch operations
- `LIST_GEMS`, `CREATE_GEM`, `UPDATE_GEM`, `DELETE_GEM`, etc.

### 3.8. Exceptions (`exceptions.py`)

**Hệ thống exception phân cấp**:

```
Exception
├── AuthError              # Lỗi authentication
├── APIError               # Lỗi package-level
│   └── ImageGenerationError
└── GeminiError           # Lỗi từ Gemini server
    ├── TimeoutError
    ├── UsageLimitExceeded
    ├── ModelInvalid
    └── TemporarilyBlocked
```

### 3.9. Utilities

#### 3.9.1. Decorators (`utils/decorators.py`)
- **@running**: Decorator kiểm tra client đang chạy, tự động re-init nếu cần, hỗ trợ retry

#### 3.9.2. Cookie Management
- **get_access_token**: Lấy SNlM0e token từ Gemini
- **load_browser_cookies**: Tự động load cookies từ browser (nếu có browser-cookie3)
- **rotate_1psidts**: Làm mới `__Secure-1PSIDTS` cookie

#### 3.9.3. File Handling
- **upload_file**: Upload file lên Google và lấy file ID
- **parse_file_name**: Parse tên file từ path

#### 3.9.4. Parsing
- **extract_json_from_response**: Extract JSON từ response text (có thể chứa nhiều JSON chunks)
- **get_nested_value**: Lấy giá trị từ nested structure an toàn

#### 3.9.5. Logging
- **logger**: Loguru logger instance
- **set_log_level**: Set log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)

---

## 4. LUỒNG HOẠT ĐỘNG

### 4.1. Khởi tạo Client

```
1. User tạo GeminiClient với cookies (hoặc để trống nếu có browser-cookie3)
2. Gọi client.init()
   ├── get_access_token() → Lấy SNlM0e token
   ├── Tạo httpx.AsyncClient với cookies và headers
   ├── Setup auto-refresh task (nếu enabled)
   └── Setup auto-close task (nếu enabled)
3. Client sẵn sàng sử dụng
```

### 4.2. Generate Content

```
1. User gọi client.generate_content(prompt, files, model, gem)
2. @running decorator kiểm tra client._running
3. Nếu có files → upload_file() cho mỗi file
4. Build request payload với:
   - Access token
   - Prompt + files (nếu có)
   - Chat metadata (nếu có)
   - Gem ID (nếu có)
5. POST request đến Endpoint.GENERATE với model headers
6. Parse response:
   ├── Extract JSON từ response text
   ├── Tìm body chứa candidates
   ├── Parse từng candidate:
   │   ├── Text output
   │   ├── Thoughts (nếu có)
   │   ├── Web images
   │   └── Generated images (parse riêng từ response)
   └── Tạo ModelOutput với candidates
7. Return ModelOutput
```

### 4.3. Chat Session

```
1. User tạo chat = client.start_chat(model, gem, metadata)
2. User gọi chat.send_message(prompt)
   ├── Gọi client.generate_content() với chat metadata
   ├── Cập nhật chat.last_output
   └── Tự động update chat.metadata từ response
3. User có thể chọn candidate khác: chat.choose_candidate(index)
4. Tiếp tục conversation với metadata đã cập nhật
```

### 4.4. Auto-Refresh Cookies

```
1. Background task start_auto_refresh() chạy mỗi refresh_interval giây
2. Gọi rotate_1psidts() để lấy cookie mới
3. Cập nhật client.cookies và client.client.cookies
4. Nếu lỗi AuthError → Cancel task
```

### 4.5. Gem Management

```
1. Fetch gems:
   ├── Gọi _batch_execute() với RPC LIST_GEMS (2 requests: system + custom)
   ├── Parse response để lấy predefined và custom gems
   └── Cache vào client._gems (GemJar)

2. Create gem:
   ├── Gọi _batch_execute() với RPC CREATE_GEM
   └── Return Gem object mới

3. Update/Delete gem:
   └── Tương tự với RPC UPDATE_GEM hoặc DELETE_GEM
```

---

## 5. CÁC TÍNH NĂNG NỔI BẬT

### 5.1. Persistent Cookies
- Tự động refresh cookies trong background
- Tối ưu cho always-on services
- Hỗ trợ lưu cookies vào file (qua env var `GEMINI_COOKIE_PATH`)

### 5.2. Image Generation
- Hỗ trợ native image generation với Nano Banana (ImageFX)
- Phân biệt WebImage và GeneratedImage
- Hỗ trợ lưu images với full-size option

### 5.3. System Prompt (Gems)
- Hỗ trợ Gemini Gems để customize system prompt
- Quản lý custom gems (create, update, delete)
- Filter và search gems

### 5.4. Extension Support
- Hỗ trợ Gemini Extensions (YouTube, Gmail, etc.)
- Sử dụng "@ExtensionName" syntax

### 5.5. Classified Outputs
- Phân loại outputs: text, thoughts, web images, generated images
- Hỗ trợ multiple candidates
- Có thể chọn candidate khác để tiếp tục conversation

### 5.6. Official Flavor API
- Interface tương tự Google Generative AI official API
- Dễ dàng migrate từ official API

### 5.7. Asynchronous
- Sử dụng `asyncio` và `httpx` cho async operations
- Hiệu quả cho concurrent requests

---

## 6. XỬ LÝ LỖI

### 6.1. Error Handling Strategy

1. **AuthError**: Cookies không hợp lệ → User cần re-authenticate
2. **APIError**: Lỗi package-level → Có thể retry hoặc re-init
3. **GeminiError**: Lỗi từ server → Xử lý theo error code
   - `UsageLimitExceeded`: Đổi model khác
   - `ModelInvalid`: Model không available
   - `TemporarilyBlocked`: Dùng proxy hoặc đợi
   - `TimeoutError`: Tăng timeout

### 6.2. Retry Mechanism

- `@running` decorator hỗ trợ retry với `retry` parameter
- Image generation chỉ retry 1 lần (vì mất thời gian)
- Tự động re-init client nếu không running

### 6.3. Error Recovery

- Client tự động đóng và re-init khi gặp lỗi nghiêm trọng
- Auto-refresh task tự cancel khi gặp AuthError
- Logging chi tiết để debug

---

## 7. BẢO MẬT VÀ PRIVACY

### 7.1. Authentication
- Sử dụng cookies từ browser session
- Access token (SNlM0e) được lấy tự động
- Cookies được refresh tự động

### 7.2. Cookie Management
- Cookies có thể lưu vào file (Docker volumes)
- Hỗ trợ load từ browser (browser-cookie3)
- Auto-refresh để tránh expiration

### 7.3. Privacy Considerations
- Auto-refresh có thể khiến user phải re-login browser
- Khuyến nghị dùng separate browser session
- Cookies không được log

---

## 8. TESTING

### 8.1. Test Structure
- Sử dụng `unittest.IsolatedAsyncioTestCase`
- Test các tính năng chính:
  - Successful requests
  - Model switching
  - File upload
  - Continuous conversation
  - Image generation
  - Gem management

### 8.2. Test Environment
- Cần environment variables: `SECURE_1PSID`, `SECURE_1PSIDTS`
- Skip tests nếu authentication fails

---

## 9. DEPLOYMENT VÀ USAGE

### 9.1. Installation
```bash
pip install -U gemini-webapi
# Optional: for browser cookie support
pip install -U browser-cookie3
```

### 9.2. Basic Usage
```python
import asyncio
from gemini_webapi import GeminiClient

async def main():
    client = GeminiClient(Secure_1PSID, Secure_1PSIDTS)
    await client.init()
    
    response = await client.generate_content("Hello!")
    print(response.text)
    
    await client.close()

asyncio.run(main())
```

### 9.3. Docker Deployment
- Set `GEMINI_COOKIE_PATH` environment variable
- Mount volume để persist cookies
- Auto-refresh hoạt động trong container

---

## 10. HẠN CHẾ VÀ LƯU Ý

### 10.1. Limitations
- Reverse-engineered API → Có thể break khi Google thay đổi
- Image generation có giới hạn theo region/account
- Extensions có giới hạn ngôn ngữ/khu vực
- Một số models yêu cầu advanced account

### 10.2. Best Practices
- Sử dụng separate browser session cho cookies
- Set reasonable timeout cho requests
- Enable auto-refresh cho always-on services
- Handle exceptions properly
- Monitor cookie expiration

### 10.3. Known Issues
- Auto-refresh có thể khiến browser session logout
- Batch execution invalidate access token
- Một số models có thể không available

---

## 11. KẾT LUẬN

### 11.1. Điểm mạnh
- ✅ Interface đơn giản, dễ sử dụng
- ✅ Hỗ trợ đầy đủ tính năng của Gemini web app
- ✅ Auto-refresh cookies cho always-on services
- ✅ Hỗ trợ async, hiệu quả
- ✅ Type hints đầy đủ với Pydantic
- ✅ Error handling tốt

### 11.2. Điểm cần cải thiện
- ⚠️ Phụ thuộc vào reverse-engineered API
- ⚠️ Cần cập nhật khi Google thay đổi
- ⚠️ Documentation có thể chi tiết hơn

### 11.3. Use Cases
- Chatbots và conversational AI
- Content generation
- Image generation và editing
- File analysis (PDF, images)
- Integration với Gemini Extensions

---

## 12. TÀI LIỆU THAM KHẢO

- [Google Gemini](https://gemini.google.com)
- [Google Generative AI](https://ai.google.dev)
- [GitHub Repository](https://github.com/HanaokaYuzu/Gemini-API)
- [PyPI Package](https://pypi.org/project/gemini-webapi)

---

**Tài liệu này được tạo tự động để phân tích và hệ thống hóa toàn bộ repository Gemini-API.**

