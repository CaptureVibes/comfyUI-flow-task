<template>
  <div class="dash-home">
    <div class="greeting-block">
      <div class="greeting-emoji">{{ greeting.emoji }}</div>
      <h1 class="greeting-title">{{ greeting.text }}</h1>
      <p class="greeting-sub">{{ greeting.sub }}</p>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const greeting = computed(() => {
  const h = new Date().getHours()
  if (h >= 0 && h < 5)   return { text: '夜深了，注意休息', emoji: '🌙', sub: '身体是革命的本钱，明天的任务明天再说' }
  if (h >= 5 && h < 9)   return { text: '早上好，新的一天开始了', emoji: '🌅', sub: '记得吃早饭，元气满满地迎接今天' }
  if (h >= 9 && h < 12)  return { text: '上午好，状态不错吧', emoji: '☀️', sub: '趁着上午精力充沛，把重要的事先做掉' }
  if (h >= 12 && h < 14) return { text: '中午了，该休息一下', emoji: '🍱', sub: '去吃个饭吧，下午的你会感谢现在的你' }
  if (h >= 14 && h < 18) return { text: '下午好，继续加油', emoji: '⚡', sub: '下午容易犯困，来杯水提提神' }
  if (h >= 18 && h < 21) return { text: '晚上好，辛苦了', emoji: '🌆', sub: '工作了一天，记得给自己留点放松的时间' }
  return { text: '还没睡呀，早点休息', emoji: '🦉', sub: '适当休息才能走得更远，明天见' }
})
</script>

<style scoped>
.dash-home {
  min-height: calc(100vh - 120px);
  display: flex;
  align-items: center;
  justify-content: center;
  font-family: 'Inter', system-ui, sans-serif;
}
.greeting-block {
  text-align: center;
}
.greeting-emoji {
  font-size: 52px;
  margin-bottom: 20px;
  line-height: 1;
}
.greeting-title {
  font-size: 32px;
  font-weight: 800;
  color: #0f172a;
  letter-spacing: -0.04em;
  margin-bottom: 12px;
}
.greeting-sub {
  font-size: 16px;
  color: #94a3b8;
  font-weight: 400;
}
</style>
