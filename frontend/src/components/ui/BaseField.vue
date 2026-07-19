<script setup lang="ts">
const props = withDefaults(defineProps<{
  modelValue: string;
  label: string;
  name: string;
  type?: string;
  autocomplete?: string;
  placeholder?: string;
  required?: boolean;
  minlength?: number;
  maxlength?: number;
  inputmode?: "text" | "email" | "numeric";
}>(), { type: "text", autocomplete: "off", placeholder: "", required: false });

const emit = defineEmits<{ "update:modelValue": [value: string] }>();
</script>

<template>
  <label class="base-field">
    <span class="base-field__label">{{ label }}</span>
    <input
      :value="props.modelValue"
      :name="name"
      :type="type"
      :autocomplete="autocomplete"
      :placeholder="placeholder"
      :required="required"
      :minlength="minlength"
      :maxlength="maxlength"
      :inputmode="inputmode"
      @input="emit('update:modelValue', ($event.target as HTMLInputElement).value)"
    />
  </label>
</template>
