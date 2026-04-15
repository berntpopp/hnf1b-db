<template>
  <v-card v-if="items.length > 0" class="mention-suggestions elevation-4">
    <v-list density="compact" nav>
      <v-list-item
        v-for="(item, i) in items"
        :key="item.id"
        :active="i === selectedIndex"
        @click="selectItem(i)"
      >
        <v-list-item-title>@{{ item.username }}</v-list-item-title>
        <v-list-item-subtitle v-if="item.display_name">
          {{ item.display_name }}
        </v-list-item-subtitle>
      </v-list-item>
    </v-list>
  </v-card>
</template>

<script setup>
import { ref, watch } from 'vue';

const props = defineProps({
  items: { type: Array, required: true },
  command: { type: Function, required: true },
});

const selectedIndex = ref(0);

watch(
  () => props.items,
  (next) => {
    if (selectedIndex.value >= next.length) selectedIndex.value = 0;
  }
);

const selectItem = (i) => {
  const item = props.items[i];
  if (item) {
    props.command({ id: item.id, label: item.username });
  }
};

const upHandler = () => {
  if (props.items.length === 0) return;
  selectedIndex.value = (selectedIndex.value + props.items.length - 1) % props.items.length;
};

const downHandler = () => {
  if (props.items.length === 0) return;
  selectedIndex.value = (selectedIndex.value + 1) % props.items.length;
};

const enterHandler = () => {
  if (props.items.length === 0) return;
  selectItem(selectedIndex.value);
};

const onKeyDown = ({ event }) => {
  if (event.key === 'ArrowUp') {
    upHandler();
    return true;
  }
  if (event.key === 'ArrowDown') {
    downHandler();
    return true;
  }
  if (event.key === 'Enter') {
    enterHandler();
    return true;
  }
  return false;
};

defineExpose({ onKeyDown });
</script>

<style scoped>
.mention-suggestions {
  position: absolute;
  z-index: 100;
  max-width: 320px;
  max-height: 240px;
  overflow-y: auto;
}
</style>
