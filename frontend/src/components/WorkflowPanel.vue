<template>
  <section class="workflow-panel">
    <div class="workflow-panel-header">
      <div>
        <h3>LangGraph 并行工作流</h3>
        <p>{{ completedWorkflowNodes }} / {{ visibleWorkflowNodes.length }} 节点完成 · {{ workflowEdges.length }} 条边</p>
      </div>
      <button class="secondary-btn workflow-toggle" type="button" @click="$emit('update:collapsed', !collapsed)">
        {{ collapsed ? "展开流程" : "收起流程" }}
      </button>
    </div>
    <div v-show="!collapsed" class="workflow-map" role="list" aria-label="LangGraph 节点图">
      <div class="workflow-global-row">
        <button
          v-for="node in globalWorkflowNodes"
          :key="node.key"
          type="button"
          :class="['graph-node', node.status, { selected: node.id === selectedWorkflowNodeId }]"
          @click="$emit('select-node', node.id)"
        >
          <span class="graph-node-dot"></span>
          <strong>{{ node.label }}</strong>
          <small>{{ node.detail || formatWorkflowStatus(node.status) }}</small>
        </button>
      </div>

      <div class="workflow-lanes" v-if="taskWorkflowRows.length">
        <section
          v-for="row in taskWorkflowRows"
          :key="row.task.id"
          class="workflow-lane"
        >
          <button
            type="button"
            class="workflow-lane-label"
            @click="$emit('select-task', row.task.id)"
          >
            <span>任务 {{ row.task.id }}</span>
            <strong>{{ row.task.title }}</strong>
          </button>
          <div class="workflow-lane-nodes">
            <button
              v-for="node in row.nodes"
              :key="node.key"
              type="button"
              :class="['graph-node', 'task-node', node.status, { selected: node.id === selectedWorkflowNodeId }]"
              @click="selectTaskNode(node)"
            >
              <span class="graph-node-dot"></span>
              <strong>{{ node.label }}</strong>
              <small>{{ node.detail || formatWorkflowStatus(node.status) }}</small>
            </button>
          </div>
        </section>
      </div>

      <div class="workflow-global-row report-row">
        <button
          v-for="node in reportWorkflowNodes"
          :key="node.key"
          type="button"
          :class="['graph-node', node.status, { selected: node.id === selectedWorkflowNodeId }]"
          @click="$emit('select-node', node.id)"
        >
          <span class="graph-node-dot"></span>
          <strong>{{ node.label }}</strong>
          <small>{{ node.detail || formatWorkflowStatus(node.status) }}</small>
        </button>
      </div>
    </div>
  </section>
</template>

<script lang="ts" setup>
import type { TodoTaskView, WorkflowEdgeView, WorkflowNodeView } from "../types";

interface WorkflowRow {
  task: TodoTaskView;
  nodes: WorkflowNodeView[];
}

defineProps<{
  collapsed: boolean;
  completedWorkflowNodes: number;
  visibleWorkflowNodes: WorkflowNodeView[];
  workflowEdges: WorkflowEdgeView[];
  globalWorkflowNodes: WorkflowNodeView[];
  taskWorkflowRows: WorkflowRow[];
  reportWorkflowNodes: WorkflowNodeView[];
  selectedWorkflowNodeId: string | null;
  formatWorkflowStatus: (status: string) => string;
}>();

const emit = defineEmits<{
  "update:collapsed": [value: boolean];
  "select-node": [nodeId: string];
  "select-task": [taskId: number];
}>();

function selectTaskNode(node: WorkflowNodeView) {
  emit("select-node", node.id);
  if (node.taskId !== null) {
    emit("select-task", node.taskId);
  }
}
</script>