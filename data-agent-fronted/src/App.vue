<template>
  <div class="chat-page">
    <!-- 消息区 -->
    <div ref="messagesEl" class="messages">
      <div
          v-for="(msg, index) in messages"
          :key="index"
          :class="['message-row', msg.role]"
      >
        <div v-if="msg.role === 'assistant'" class="avatar assistant-avatar">🤖</div>

        <div class="bubble">
          <!-- 文本 -->
          <div v-if="msg.type === 'text'" class="text-content">
            {{ msg.content }}
          </div>

          <!-- 进度步骤 -->
          <div v-else-if="msg.type === 'steps'" class="steps">
            <div v-for="(step, sIdx) in msg.steps" :key="sIdx" class="step">
              <span class="dot" :class="step.status"></span>
              <span class="step-text">{{ step.text }}</span>
            </div>
          </div>

          <!-- 表格 -->
          <div v-else-if="msg.type === 'table'" class="table-wrap">
            <table class="result-table">
              <thead>
              <tr>
                <th v-for="col in msg.columns" :key="col">
                  {{ col }}
                </th>
              </tr>
              </thead>
              <tbody>
              <tr v-for="(row, rIdx) in msg.rows" :key="rIdx">
                <td v-for="col in msg.columns" :key="col">
                  {{ row[col] }}
                </td>
              </tr>
              </tbody>
            </table>
          </div>

          <!-- 错误 -->
          <div v-else-if="msg.type === 'error'" class="error-text">
            ⚠️ {{ msg.content }}
          </div>
        </div>

        <div v-if="msg.role === 'user'" class="avatar user-avatar">🧑</div>
      </div>
      <div class="messages-bottom-spacer"></div>
    </div>

    <!-- 悬浮输入框 -->
    <div class="input-wrapper">
      <div class="input-box">
        <input
            v-model="question"
            @keyup.enter="sendQuestion"
            placeholder="请输入你的数据分析问题（如：上个月各地区的总收入是多少？）..."
        />
        <button @click="sendQuestion" :disabled="loading">
          <span v-if="loading" class="loading-spinner"></span>
          {{ loading ? "思考中..." : "发送" }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import {nextTick, ref} from "vue";

const API_URL = "/api/query";

const question = ref("");
const loading = ref(false);
const messages = ref([]);
const messagesEl = ref(null);

function scrollToBottom() {
  const el = messagesEl.value;
  if (!el) return;
  el.scrollTop = el.scrollHeight;
}

async function sendQuestion() {
  if (!question.value || loading.value) return;

  const q = question.value;
  question.value = "";
  loading.value = true;

  messages.value.push({role: "user", type: "text", content: q});

  // steps 容器
  const stepIndex =
      messages.value.push({
        role: "assistant",
        type: "steps",
        steps: [],
      }) - 1;

  await nextTick();
  scrollToBottom();

  try {
    const response = await fetch(API_URL, {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({query: q}),
    });

    if (!response.body) throw new Error("服务器未返回流");

    const reader = response.body.getReader();
    const decoder = new TextDecoder("utf-8");
    let buffer = "";

    while (true) {
      const {value, done} = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, {stream: true});
      const events = buffer.split("\n\n");
      buffer = events.pop();

      for (const evt of events) {
        const line = evt.trim();
        if (!line.startsWith("data:")) continue;

        let data;
        try {
          data = JSON.parse(line.replace(/^data:\s*/, ""));
        } catch {
          continue;
        }

        const steps = messages.value[stepIndex].steps;

        // ✅ progress：完全按后端状态渲染
        if (data.type === "progress") {
          let step = steps.find((s) => s.text === data.step);

          if (!step) {
            step = {
              text: data.step,
              status: data.status,
            };
            steps.push(step);
          } else {
            step.status = data.status;
          }
        }

        // ✅ 表格结果
        else if (data.type === "result" && Array.isArray(data.data)) {
          messages.value.push({
            role: "assistant",
            type: "table",
            columns: Object.keys(data.data[0] || {}),
            rows: data.data,
          });
        }

        // ✅ 错误
        else if (data.type === "error") {
          messages.value.push({
            role: "assistant",
            type: "error",
            content: data.message || "发生错误",
          });
        }

        await nextTick();
        scrollToBottom();
      }
    }
  } catch (e) {
    messages.value.push({
      role: "assistant",
      type: "error",
      content: e?.message || "请求失败",
    });
  } finally {
    loading.value = false;
    await nextTick();
    scrollToBottom();
  }
}
</script>

<style scoped>
/* 全局基础重置与滚动条美化 */
:global(html),
:global(body) {
  height: 100%;
  margin: 0;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
  color: #1f2937;
  background-color: #f8fafc;
}

:global(body) {
  display: block !important;
  place-items: unset !important;
}

:global(#app) {
  height: 100%;
  max-width: none !important;
  margin: 0 !important;
  padding: 0 !important;
}

/* 自定义美观滚动条 */
::-webkit-scrollbar {
  width: 6px;
  height: 6px;
}
::-webkit-scrollbar-track {
  background: transparent;
}
::-webkit-scrollbar-thumb {
  background: #cbd5e1;
  border-radius: 3px;
}
::-webkit-scrollbar-thumb:hover {
  background: #94a3b8;
}

/* 页面主体 */
.chat-page {
  height: 100%;
  overflow: hidden;
  background: #fdfdfd;
  position: relative;
}

/* 消息区 */
.messages {
  height: 100%;
  overflow-y: auto;
  padding: 24px 15% 160px;
  box-sizing: border-box;
  scroll-behavior: smooth;
}

.message-row {
  display: flex;
  margin-bottom: 20px;
  animation: fadeIn 0.3s ease-out;
}

@keyframes fadeIn {
  from { opacity: 0; transform: translateY(8px); }
  to { opacity: 1; transform: translateY(0); }
}

.message-row.assistant {
  justify-content: flex-start;
}

.message-row.user {
  justify-content: flex-end;
}

/* 头像升级 */
.avatar {
  width: 38px;
  height: 38px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 18px;
  flex-shrink: 0;
  box-shadow: 0 2px 6px rgba(0, 0, 0, 0.04);
}

.assistant-avatar {
  background: linear-gradient(135deg, #eff6ff 0%, #dbeafe 100%);
  border: 1px solid #bfdbfe;
}

.user-avatar {
  background: linear-gradient(135deg, #f1f5f9 0%, #e2e8f0 100%);
  border: 1px solid #cbd5e1;
}

/* 气泡样式重构 */
.bubble {
  max-width: min(820px, 75%);
  padding: 14px 18px;
  border-radius: 16px;
  background: #ffffff;
  border: 1px solid #f1f5f9;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.03);
  font-size: 14.5px;
  line-height: 1.6;
}

.message-row.user .bubble {
  background: #2563eb;
  color: #ffffff;
  border: none;
  border-top-right-radius: 4px;
  box-shadow: 0 4px 12px rgba(37, 99, 235, 0.15);
}

.message-row.assistant .bubble {
  border-top-left-radius: 4px;
}

.text-content {
  white-space: pre-wrap;
  word-break: break-word;
}

/* 步骤条卡片化 */
.steps {
  display: flex;
  flex-direction: column;
  gap: 10px;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  padding: 12px 16px;
  border-radius: 10px;
}

.step {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 13.5px;
  color: #475569;
}

.step-text {
  font-weight: 500;
}

/* 状态灯动画 */
.dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  position: relative;
}

.dot.running {
  background: #f59e0b;
  box-shadow: 0 0 0 3px rgba(245, 158, 11, 0.15);
  animation: pulse 1.5s infinite ease-in-out;
}

@keyframes pulse {
  0% { transform: scale(0.95); opacity: 0.8; }
  50% { transform: scale(1.15); opacity: 1; box-shadow: 0 0 0 6px rgba(245, 158, 11, 0.1); }
  100% { transform: scale(0.95); opacity: 0.8; }
}

.dot.success {
  background: #10b981;
  box-shadow: 0 0 0 3px rgba(16, 185, 129, 0.15);
}

.dot.error {
  background: #ef4444;
  box-shadow: 0 0 0 3px rgba(239, 68, 68, 0.15);
}

/* 表格容器高颜值设计 */
.table-wrap {
  max-width: 100%;
  overflow-x: auto;
  border-radius: 8px;
  border: 1px solid #e2e8f0;
  background: #ffffff;
  margin-top: 4px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.02);
}

.result-table {
  width: max-content;
  min-width: 100%;
  table-layout: auto;
  border-collapse: collapse;
}

.result-table th,
.result-table td {
  border-bottom: 1px solid #f1f5f9;
  border-right: 1px solid #f8fafc;
  padding: 10px 14px;
  white-space: nowrap;
  font-size: 13px;
  text-align: left;
}

.result-table tbody tr:hover {
  background-color: #f8fafc;
}

.result-table th {
  background: #f8fafc;
  color: #334155;
  font-weight: 600;
  position: sticky;
  top: 0;
  z-index: 1;
  border-bottom: 2px solid #e2e8f0;
}

/* 错误提示美化 */
.error-text {
  color: #dc2626;
  font-weight: 500;
  display: flex;
  align-items: center;
  gap: 6px;
}

/* 悬浮输入框高定升级 */
.input-wrapper {
  position: fixed;
  left: 0;
  right: 0;
  bottom: 28px;
  display: flex;
  justify-content: center;
  padding: 0 20px;
  pointer-events: none;
  z-index: 10;
}

.input-box {
  pointer-events: auto;
  width: 100%;
  max-width: 760px;
  display: flex;
  gap: 12px;
  padding: 10px 10px 10px 20px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.85);
  backdrop-filter: blur(16px);
  -webkit-backdrop-filter: blur(16px);
  border: 1px solid rgba(226, 232, 240, 0.8);
  box-shadow: 0 12px 32px rgba(15, 23, 42, 0.08), 0 2px 6px rgba(15, 23, 42, 0.04);
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

.input-box:focus-within {
  background: rgba(255, 255, 255, 0.98);
  border-color: #3b82f6;
  box-shadow: 0 16px 40px rgba(37, 99, 235, 0.12), 0 0 0 3px rgba(59, 130, 246, 0.15);
}

.input-box input {
  flex: 1;
  border: none;
  outline: none;
  background: transparent;
  font-size: 15px;
  color: #1e293b;
}

.input-box input::placeholder {
  color: #94a3b8;
}

.input-box button {
  padding: 0 22px;
  height: 42px;
  border-radius: 999px;
  border: none;
  background: linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%);
  color: #fff;
  font-weight: 500;
  font-size: 14px;
  cursor: pointer;
  transition: all 0.2s ease;
  box-shadow: 0 4px 12px rgba(37, 99, 235, 0.25);
  display: flex;
  align-items: center;
  justify-content: center;
}

.input-box button:hover:not(:disabled) {
  transform: translateY(-1px);
  box-shadow: 0 6px 16px rgba(37, 99, 235, 0.35);
}

.input-box button:active:not(:disabled) {
  transform: translateY(0);
}

.input-box button:disabled {
  opacity: 0.6;
  cursor: not-allowed;
  background: #94a3b8;
  box-shadow: none;
}

.messages-bottom-spacer {
  height: 120px;
}
</style>