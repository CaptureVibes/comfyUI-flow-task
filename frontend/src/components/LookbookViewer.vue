<template>
  <div class="lookbook-viewer">
    <!-- 标题 + 重生成 -->
    <div class="lb-header">
      <span class="lb-title">造型 {{ String(outfitIndex + 1).padStart(2, '0') }}</span>
      <span class="lb-stats">
        总 {{ lookbook.panels?.length || 0 }} ·
        已用 <b class="lb-used">{{ usedCount }}</b> ·
        剩余 <b class="lb-remain">{{ remainingCount }}</b>
        <span v-if="lookbook.regenerated_count" class="lb-regen-tag">已重生成 ×{{ lookbook.regenerated_count }}</span>
      </span>
      <button
        class="lb-regen-btn"
        :disabled="regenerating"
        @click="$emit('regenerate', outfitIndex)"
      >{{ regenerating ? '重生成中…' : '重生成 lookbook' }}</button>
    </div>

    <!-- 三栏：输入 / 4×2 lookbook / 8 panel -->
    <div class="lb-grid">
      <div class="lb-col lb-col-input">
        <div class="lb-col-label">① 输入造型截图</div>
        <img
          v-if="lookbook.outfit_shot_image_url"
          :src="lookbook.outfit_shot_image_url"
          class="lb-input-image"
          alt="input"
        />
        <div v-else class="lb-empty">无输入图</div>
      </div>

      <div class="lb-col lb-col-collage">
        <div class="lb-col-label">② 4×2 八拼图</div>
        <img
          v-if="lookbook.lookbook_image_url"
          :src="lookbook.lookbook_image_url"
          class="lb-collage-image"
          alt="lookbook"
        />
        <div v-else class="lb-empty">无 lookbook 图</div>
        <div v-if="lookbook.generated_prompt" class="lb-prompt" :title="lookbook.generated_prompt">
          生图 Prompt: {{ lookbook.generated_prompt.slice(0, 60) }}...
        </div>
      </div>

      <div class="lb-col lb-col-panels">
        <div class="lb-col-label">③ 拆分后的 8 张造型图</div>
        <div class="lb-panel-grid">
          <div
            v-for="panel in lookbook.panels || []"
            :key="panel.index"
            class="lb-panel"
            :class="[
              panel.is_reference ? 'is-reference' : '',
              panel.used_in_remix_id ? 'is-used' : 'is-unused',
            ]"
          >
            <div class="lb-panel-thumb">
              <img v-if="panel.image_url" :src="panel.image_url" :alt="`panel ${panel.index}`" />
            </div>
            <div class="lb-panel-body">
              <div class="lb-panel-name">造型图 {{ String(panel.index).padStart(2, '0') }}</div>
              <span v-if="panel.is_reference" class="lb-panel-badge is-ref">参考图</span>
              <span v-else-if="panel.used_in_remix_id" class="lb-panel-badge is-done">已使用</span>
              <span v-else class="lb-panel-badge is-todo">未使用</span>
              <button
                v-if="!panel.is_reference && !panel.used_in_remix_id"
                class="lb-panel-btn"
                :disabled="remixingPanel === panel.index"
                @click="$emit('remix', { outfitIndex, panelIndex: panel.index })"
              >{{ remixingPanel === panel.index ? '提交中…' : '用于重洗' }}</button>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  outfitIndex: { type: Number, required: true },
  lookbook: { type: Object, required: true },
  remixingPanel: { type: Number, default: null },
  regenerating: { type: Boolean, default: false },
})

defineEmits(['remix', 'regenerate'])

const usedCount = computed(() =>
  (props.lookbook.panels || []).filter(p => !p.is_reference && p.used_in_remix_id).length
)
const remainingCount = computed(() =>
  (props.lookbook.panels || []).filter(p => !p.is_reference && !p.used_in_remix_id).length
)
</script>

<style scoped>
.lookbook-viewer {
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  padding: 16px;
  background: #fff;
  margin-bottom: 16px;
}

.lb-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
  font-size: 13px;
}
.lb-title { font-weight: 600; color: #0f172a; font-size: 14px; }
.lb-stats { color: #64748b; flex: 1; }
.lb-used { color: #b45309; }
.lb-remain { color: #059669; }
.lb-regen-tag {
  margin-left: 8px;
  padding: 1px 6px;
  background: #f1f5f9;
  color: #475569;
  border-radius: 4px;
  font-size: 11px;
}
.lb-regen-btn {
  padding: 4px 12px;
  border: 1px solid #cbd5e1;
  background: #fff;
  border-radius: 6px;
  cursor: pointer;
  font-size: 12px;
}
.lb-regen-btn:hover:not(:disabled) { background: #f1f5f9; border-color: #6366f1; color: #4338ca; }
.lb-regen-btn:disabled { opacity: 0.6; cursor: not-allowed; }

.lb-grid {
  display: grid;
  grid-template-columns: 1fr 1fr 2fr;
  gap: 16px;
}
.lb-col { display: flex; flex-direction: column; gap: 6px; }
.lb-col-label {
  font-weight: 600; font-size: 12px; color: #475569;
}
.lb-input-image, .lb-collage-image {
  width: 100%;
  border-radius: 6px;
  object-fit: contain;
  background: #f8fafc;
}
.lb-empty {
  display: flex; align-items: center; justify-content: center;
  height: 200px; background: #f8fafc; border-radius: 6px;
  color: #94a3b8; font-size: 12px;
}
.lb-prompt {
  font-size: 11px; color: #64748b;
  word-break: break-all; line-height: 1.4;
}

.lb-panel-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 8px;
}
.lb-panel {
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  overflow: hidden;
  background: #fff;
  display: flex;
  flex-direction: column;
}
.lb-panel.is-reference { border-color: #94a3b8; background: #f8fafc; }
.lb-panel.is-used { opacity: 0.7; }
.lb-panel-thumb {
  aspect-ratio: 9 / 16;
  background: #f1f5f9;
  overflow: hidden;
}
.lb-panel-thumb img { width: 100%; height: 100%; object-fit: cover; }
.lb-panel-body { padding: 6px 8px; display: flex; flex-direction: column; gap: 4px; }
.lb-panel-name { font-size: 11px; font-weight: 600; color: #0f172a; }
.lb-panel-badge {
  display: inline-block;
  padding: 1px 6px;
  border-radius: 3px;
  font-size: 10px;
  font-weight: 500;
  align-self: flex-start;
}
.lb-panel-badge.is-ref { background: #f1f5f9; color: #475569; }
.lb-panel-badge.is-done { background: #dcfce7; color: #15803d; }
.lb-panel-badge.is-todo { background: #fef3c7; color: #b45309; }
.lb-panel-btn {
  margin-top: 4px;
  padding: 3px 8px;
  border: 1px solid #6366f1;
  background: #fff;
  color: #4338ca;
  border-radius: 4px;
  font-size: 11px;
  cursor: pointer;
}
.lb-panel-btn:hover:not(:disabled) { background: #eef2ff; }
.lb-panel-btn:disabled { opacity: 0.6; cursor: not-allowed; }
</style>
