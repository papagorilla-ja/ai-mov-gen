<template>
  <div>
    <div class="text-caption text-medium-emphasis mb-2">アバターを選択</div>
    <div class="avatar-grid">
      <div
        v-for="n in 20"
        :key="n"
        class="avatar-cell"
        :class="{ 'avatar-selected': modelValue === avatarFilename(n) }"
        @click="select(n)"
      >
        <img
          :src="avatarUrl(n)"
          :alt="`avatar_${String(n).padStart(2, '0')}`"
          class="avatar-img"
        />
        <v-icon v-if="modelValue === avatarFilename(n)" class="check-icon" color="white" size="18">
          mdi-check-circle
        </v-icon>
      </div>
      <!-- アバターなし（リセット）選択肢 -->
      <div
        class="avatar-cell avatar-none"
        :class="{ 'avatar-selected': !modelValue }"
        @click="$emit('update:modelValue', null)"
      >
        <v-icon size="32" color="grey">mdi-account-circle-outline</v-icon>
        <div class="text-caption mt-1" style="font-size: 9px;">なし</div>
      </div>
    </div>
  </div>
</template>

<script setup>
const props = defineProps({
  modelValue: { type: String, default: null }
})
const emit = defineEmits(['update:modelValue'])

function avatarFilename(n) {
  return `avatar_${String(n).padStart(2, '0')}.jpg`
}

function avatarUrl(n) {
  return `/static/avatars/${avatarFilename(n)}`
}

function select(n) {
  emit('update:modelValue', avatarFilename(n))
}
</script>

<style scoped>
.avatar-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 8px;
}

.avatar-cell {
  position: relative;
  border-radius: 50%;
  cursor: pointer;
  border: 2px solid transparent;
  transition: border-color 0.2s, transform 0.15s;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  aspect-ratio: 1;
  overflow: hidden;
}

.avatar-cell:hover {
  transform: scale(1.08);
  border-color: rgba(var(--v-theme-primary), 0.5);
}

.avatar-selected {
  border-color: rgb(var(--v-theme-primary)) !important;
  box-shadow: 0 0 0 2px rgb(var(--v-theme-primary));
}

.avatar-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  border-radius: 50%;
}

.avatar-none {
  background: rgba(128, 128, 128, 0.15);
  border-radius: 50%;
}

.check-icon {
  position: absolute;
  bottom: 2px;
  right: 2px;
  background: rgb(var(--v-theme-primary));
  border-radius: 50%;
}
</style>
