<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { ArrowDown, ArrowLeft, ArrowRight, ArrowUp, Files, Tickets, RefreshRight, SetUp } from '@element-plus/icons-vue'
import { getProjectBatch, type BatchView } from '@/api/project'
import { createAiTask, getLatestAiTask } from '@/api/ai/task'
import { getQuantitySummary } from '@/api/raw/quantity'
import { DictConstants } from '@/constants/dict'
import { getDictChildren } from '@/utils/dict'
import { useAiProcessingStore } from '@/store/modules/integration/aiProcessing'
import AiProcessingOverlay from '@/components/AiProcessingOverlay.vue'
import CbsBuildPanel from './cbs/CbsBuildPanel.vue'
import FeeInfoPanel from './fee/FeeInfoPanel.vue'
import MaterialFilePanel from './material/MaterialFilePanel.vue'
import QuantityPanel from './quantity/QuantityPanel.vue'
import QuotaMatchPanel from './quota/QuotaMatchPanel.vue'

/**
 * 项目构建主页面：按原型组织“创建CBS结构”流程。
 * 顶部为标题与流程步骤条，节点由数据字典（组价节点 09）驱动；
 * 批次当前节点（sc_batch.current_stage）之前的节点可点击回看，按钮按查看位置显示“下一步/重新构建”；
 * 批次过了人工校验后整条流程锁定，不再允许修改。下方为三个子页签。
 */
type TabKey = 'cbs' | 'fee' | 'material'

/** 流程节点：编码来自字典项 okey，名称来自字典项名称。 */
interface FlowStep {
  code: string
  label: string
}

/** 字典加载失败时的兜底节点，编码与后端 Constants.CostingStage 一致。 */
const FALLBACK_STEPS: FlowStep[] = [
  { code: DictConstants.CostingStage.CBS_EDITING, label: 'CBS构建' },
  { code: DictConstants.CostingStage.QUANTITY_EDITING, label: '工程量结构树构建' },
  { code: DictConstants.CostingStage.QUOTA_MATCHING, label: '定额/指标匹配' },
  { code: DictConstants.CostingStage.PRICE_MATCHING, label: '价格匹配' },
  { code: DictConstants.CostingStage.MANUAL_CHECKING, label: '人工校验' },
  { code: DictConstants.CostingStage.ESTIMATE_CALCULATING, label: '汇总计算' }
]

const route = useRoute()
const router = useRouter()

const projectId = computed(() => String(route.query.projectId ?? ''))
const projectName = computed(() => String(route.query.projectName ?? '未命名项目'))

/** 流程节点列表：优先取数据字典（组价节点 09），失败时用兜底节点。 */
const steps = ref<FlowStep[]>(FALLBACK_STEPS)
/** 批次当前组价节点编码（sc_batch.current_stage），无批次时默认第一个节点。 */
const currentStage = ref<string>(DictConstants.CostingStage.CBS_EDITING)
/** 用户正在查看的节点索引，默认跟随批次当前节点。 */
const viewingIndex = ref(0)

const activeTab = ref<TabKey>('cbs')
/** 顶部流程面板默认展开；收起后隐藏面板本身，仅保留浮动展开按钮。 */
const flowCollapsed = ref(false)

/** 批次当前节点索引。 */
const currentIndex = computed(() => {
  const index = steps.value.findIndex(step => step.code === currentStage.value)
  return index >= 0 ? index : 0
})

/** 工程量编制节点索引（字典 0902），用于切换主内容区布局。 */
const quantityStageIndex = computed(() =>
  steps.value.findIndex(step => step.code === DictConstants.CostingStage.QUANTITY_EDITING))

/** 定额/指标匹配节点索引（字典 0903），用于切换主内容区布局。 */
const quotaStageIndex = computed(() =>
  steps.value.findIndex(step => step.code === DictConstants.CostingStage.QUOTA_MATCHING))

/**
 * 批次是否已锁定：当前节点过了人工校验（进入汇总计算）后，
 * 本批次不再允许修改——节点不可点击、按钮隐藏。
 */
const batchLocked = computed(() => {
  const manualIndex = steps.value.findIndex(step => step.code === DictConstants.CostingStage.MANUAL_CHECKING)
  return manualIndex >= 0 && currentIndex.value > manualIndex
})

/** 右上角动作按钮：查看节点等于批次当前节点显示“下一步”，查看已完成的节点显示“重新构建”；锁定时隐藏。 */
const flowAction = computed<{ label: string; icon: typeof RefreshRight } | null>(() => {
  if (batchLocked.value) return null
  if (viewingIndex.value === currentIndex.value) {
    // 已是最后一个节点时没有“下一步”。
    return currentIndex.value >= steps.value.length - 1
      ? null
      : { label: '下一步', icon: ArrowRight }
  }
  if (viewingIndex.value < currentIndex.value) {
    return { label: '重新构建', icon: RefreshRight }
  }
  return null
})

/** 节点是否允许点击：批次未锁定且不超前于批次当前节点。 */
function canClickStep(index: number) {
  return !batchLocked.value && index <= currentIndex.value
}

/** 节点样式：查看中的蓝色高亮，批次已完成的绿色，其余灰色等待。 */
function stepClass(index: number) {
  if (index === viewingIndex.value) return ['is-active', 'is-clickable']
  if (index <= currentIndex.value) return ['is-passed', 'is-clickable']
  return ['is-wait']
}

/** 点击节点回看：只能回到批次当前节点及之前的节点；第一个节点同步切换到 CBS 页签。 */
function handleStepClick(index: number) {
  if (!canClickStep(index)) return
  viewingIndex.value = index
  if (index === 0) activeTab.value = 'cbs'
}

/** 动作按钮：CBS 节点推进时触发 AI 工程量构建，其余节点待接入。 */
const building = ref(false)

const aiProcessingStore = useAiProcessingStore()

/** 工程量编制面板引用：AI 完成后刷新面板数据。 */
const quantityPanelRef = ref<InstanceType<typeof QuantityPanel> | null>(null)

/** 轮询定时器句柄。 */
let aiPollTimer: number | null = null
/** 轮询间隔（毫秒）：约 20 秒查询一次 AI 任务状态。 */
const AI_POLL_INTERVAL = 20000
/** 当前轮询的任务类型（组价节点编码）。 */
let aiPollTaskType = ''
/** 最近一次 AI 任务的失败信息：不再弹 msg，改在流程条操作区前方红字展示。 */
const aiError = ref('')

/** 节点编码对应的节点名称（用于 loading 文案）。 */
function stageLabel(code: string) {
  return steps.value.find(step => step.code === code)?.label ?? code
}

/** 当前批次的完整视图：供子面板按批次维度查询（如工程量未挂接列表）。 */
const batchInfo = ref<BatchView | null>(null)

/** 应用批次视图：同步批次当前节点到界面。 */
function applyBatchView(batch: BatchView | null) {
  batchInfo.value = batch
  if (batch?.currentStage) {
    currentStage.value = batch.currentStage
  }
  return batch
}

/**
 * 启动 AI 任务轮询：展示遮罩并每 20 秒查询一次 sc_ai_python_task 最新任务状态。
 * status=1 且无错误 → 拉取批次数据同步节点并恢复操作；
 * status=1 但有错误 → 弹出错误提示并解除 loading，不推进节点；
 * 其他状态（status=0）继续等待。各节点的 AI 处理均复用本机制，仅文案不同。
 */
function startAiPolling(taskType: string, text?: string) {
  aiPollTaskType = taskType
  aiProcessingStore.show(text ?? `AI 正在处理「${stageLabel(taskType)}」，请稍候...`)
  if (aiPollTimer) return
  aiPollTimer = window.setInterval(async () => {
    try {
      const task = await getLatestAiTask(projectId.value, aiPollTaskType)
      if (!task || task.status === '0') return
      stopAiPolling()
      aiProcessingStore.hide()
      if (task.status === '1' && !task.errorMessage) {
        // 任务成功完成：清空历史错误并拉取批次数据同步节点（后端已推进并落库）。
        aiError.value = ''
        const batch = await getProjectBatch(projectId.value)
        applyBatchView(batch)
        viewingIndex.value = currentIndex.value
        ElMessage.success(`「${stageLabel(aiPollTaskType)}」AI 处理完成，流程节点已推进`)
        if (viewingIndex.value === quantityStageIndex.value) {
          await quantityPanelRef.value?.reload()
        }
      } else {
        // status=1 但 error_msg 非空（或其他异常状态）：红字展示错误，不弹 msg，不推进节点。
        aiError.value = `「${stageLabel(aiPollTaskType)}」AI 处理失败${task.errorMessage ? '：' + task.errorMessage : ''}`
      }
    } catch (error) {
      console.warn('轮询 AI 任务状态失败', error)
    }
  }, AI_POLL_INTERVAL)
}

function stopAiPolling() {
  if (aiPollTimer) {
    window.clearInterval(aiPollTimer)
    aiPollTimer = null
  }
}

onUnmounted(() => {
  stopAiPolling()
  // 离开本模块即停止轮询并解除遮罩：loading 只作用于项目构建页面，不影响其他模块；
  // 重新进入时 onMounted 会按最新任务状态重新开始轮询。
  aiProcessingStore.hide()
})

async function handleFlowAction() {
  if (!flowAction.value || building.value) return
  // 任务类型传下一节点：AI 处理的数据是给下一节点使用的，
  // 在 0901 点下一步应创建 0902 的任务（重新构建同理，重建的是查看节点的下一节点数据）。
  const nextStep = steps.value[viewingIndex.value + 1]
  if (!nextStep?.code) {
    ElMessage.warning('已是最后一个节点，无法创建 AI 任务')
    return
  }
  // 工程量编制 → 定额匹配：先校验当前批次是否还有未挂接数据，有则拦截不允许进入下一节点。
  if (viewingIndex.value === quantityStageIndex.value) {
    if (!batchInfo.value?.id) {
      ElMessage.warning('批次信息缺失，无法校验挂接情况')
      return
    }
    try {
      const quantitySummary = await getQuantitySummary(projectId.value, batchInfo.value.id)
      if (quantitySummary.unattachedItems > 0) {
        ElMessage.warning(`还有 ${quantitySummary.unattachedItems} 条未挂接的工程量数据，请先在工程量编制中完成挂接`)
        return
      }
    } catch (error) {
      ElMessage.error(error instanceof Error ? error.message : '挂接情况校验失败，请稍后重试')
      return
    }
  }
  building.value = true
  aiError.value = ''
  try {
    // 区分首次执行与失败重试：当前任务类型的最新任务带 errorMessage 时视为重试，
    // 后端不再改动批次 sc_file 状态（首次执行才全量置待处理）。
    let hasError = false
    try {
      const latestTask = await getLatestAiTask(projectId.value, nextStep.code)
      hasError = !!latestTask && !!latestTask.errorMessage
    } catch {
      // 查询失败按首次执行处理
    }
    await createAiTask(projectId.value, nextStep.code, hasError)
    ElMessage.success(`「${stageLabel(nextStep.code)}」任务已提交，AI 正在后台处理`)
    startAiPolling(nextStep.code)
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : 'AI 任务创建失败')
  } finally {
    building.value = false
  }
}

/** 页面加载：并行取字典节点与项目最新批次，确定流程节点名称与批次当前节点。 */
onMounted(async () => {
  if (!projectId.value) return
  try {
    const [dictItems, batch] = await Promise.all([
      getDictChildren(DictConstants.DICT_COSTING_STAGE),
      getProjectBatch(projectId.value)
    ])
    if (dictItems.length) {
      steps.value = [...dictItems]
        .sort((a, b) => (a.okey ?? '').localeCompare(b.okey ?? ''))
        .map(item => ({
          code: item.okey ?? item.ovalue ?? '',
          label: item.lable ?? item.name ?? item.okey ?? ''
        }))
    }
    applyBatchView(batch)
    viewingIndex.value = currentIndex.value
    // 恢复中断的轮询：项目存在执行中（status=0）的 AI 任务时重新开始轮询；
    // 最新任务已失败（status=1 且有错误信息）时提示用户，等待重新发起。
    const latestTask = await getLatestAiTask(projectId.value)
    if (latestTask && latestTask.status === '0') {
      startAiPolling(latestTask.taskType)
    } else if (latestTask && latestTask.status === '1' && latestTask.errorMessage) {
      aiError.value = `「${stageLabel(latestTask.taskType)}」AI 处理失败：${latestTask.errorMessage}`
    }
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '加载项目批次信息失败')
  }
})

/** 料表文件数量：由料表面板按实际加载结果上报，用于页签角标展示。 */
const materialCount = ref(0)
const feeCount = ref(0)

/** 页签定义：数字徽章展示数量，悬停提示完整状态；料表数量由面板上报。 */
const tabs = computed(() => [
  { key: 'cbs' as TabKey, label: 'CBS构建', icon: Tickets, badge: 0, badgeTip: '' },
  { key: 'fee' as TabKey, label: '取费信息配置', icon: SetUp, badge: feeCount.value, badgeTip: `已配 ${feeCount.value} 项` },
  { key: 'material' as TabKey, label: '料表文件管理', icon: Files,
    badge: materialCount.value, badgeTip: `已上传 ${materialCount.value} 项` }
])

/** 料表面板上报文件数量。 */
function handleMaterialCount(count: number) {
  materialCount.value = count
}

/** 取费面板按当前 CBS 表中已显示的模板行数上报角标数量。 */
function handleFeeCount(count: number) {
  feeCount.value = count
}

/** 返回上一页。 */
function goBack() {
  router.back()
}
</script>

<template>
  <section class="manage-page">
    <!-- 流程与内容区：AI 处理遮罩只覆盖这一块，标题与返回按钮始终可操作。 -->
    <div class="manage-stage" :class="{ 'has-collapsed-flow': flowCollapsed }">
      <section v-if="!flowCollapsed" class="manage-flow">
        <div class="manage-flow-header">
          <div class="manage-heading">
            <el-button class="manage-back" @click="goBack"><el-icon><ArrowLeft /></el-icon>返回</el-button>
            <span class="manage-title" :title="projectName">{{ projectName }}</span>
          </div>
          <div class="manage-flow-actions">
            <span v-if="aiError" class="flow-error">{{ aiError }}</span>
            <span v-if="batchLocked" class="flow-locked-tip">批次已过人工校验，流程已锁定</span>
            <el-button v-if="flowAction" type="primary" size="small" :loading="building"
              @click="handleFlowAction">
              <template v-if="!building"><el-icon><component :is="flowAction.icon" /></el-icon></template>
              {{ flowAction.label }}
            </el-button>
            <el-button class="flow-toggle" size="small" title="收起流程面板"
              aria-label="收起流程面板" aria-expanded="true" @click="flowCollapsed = true">
              <el-icon><ArrowUp /></el-icon>收起流程
            </el-button>
          </div>
        </div>
        <ol class="flow-steps">
          <li v-for="(step, index) in steps" :key="step.code" class="flow-step"
            :class="stepClass(index)" @click="handleStepClick(index)">
            <span class="flow-step-node">{{ index + 1 }}</span>
            <span class="flow-step-title">{{ step.label }}</span>
            <span v-if="index < steps.length - 1" class="flow-step-line"
              :class="{ 'is-done': index < currentIndex || index === viewingIndex }" />
          </li>
        </ol>
      </section>
      <div v-else class="flow-expand-row">
        <el-button class="flow-expand" size="small" title="展开流程面板"
          aria-label="展开流程面板" aria-expanded="false" @click="flowCollapsed = false">
          <el-icon><ArrowDown /></el-icon>展开流程
        </el-button>
      </div>

      <div class="manage-body">
        <!-- CBS 构建节点：保留模块页签布局。 -->
        <template v-if="viewingIndex === 0">
          <el-tabs v-model="activeTab" class="manage-tabs">
            <el-tab-pane v-for="tab in tabs" :key="tab.key" :name="tab.key">
              <template #label>
                <span class="manage-tab-label">
                  <el-icon class="manage-tab-icon"><component :is="tab.icon" /></el-icon>
                  {{ tab.label }}
                  <el-tooltip v-if="tab.badge > 0" :content="tab.badgeTip" placement="top">
                    <el-badge :value="tab.badge" type="danger" class="manage-tab-badge" />
                  </el-tooltip>
                </span>
              </template>
              <div class="manage-stage-body">
                <CbsBuildPanel v-if="tab.key === 'cbs' && activeTab === tab.key"
                  :project-id="projectId" :project-name="projectName" />
                <FeeInfoPanel v-else-if="tab.key === 'fee' && activeTab === tab.key"
                  :project-id="projectId" :project-name="projectName" @count-change="handleFeeCount" />
                <MaterialFilePanel v-else-if="tab.key === 'material' && activeTab === tab.key"
                  :project-id="projectId" :project-name="projectName" @count-change="handleMaterialCount" />
              </div>
            </el-tab-pane>
          </el-tabs>
        </template>

        <!-- 工程量编制节点：左侧 CBS 树 + 右侧工程量结构。 -->
        <QuantityPanel v-else-if="viewingIndex === quantityStageIndex" ref="quantityPanelRef"
          :project-id="projectId" :batch-id="batchInfo?.id" />

        <!-- 定额/指标匹配节点：左侧 CBS 树 + 右侧定额匹配树表。 -->
        <QuotaMatchPanel v-else-if="viewingIndex === quotaStageIndex"
          :project-id="projectId" :batch-id="batchInfo?.id" />

        <div v-else class="manage-placeholder">
          「{{ steps[viewingIndex]?.label ?? '该节点' }}」的功能页面待实现
        </div>
      </div>

      <!-- AI 处理中遮罩：仅覆盖流程条与内容区，返回按钮不受影响。 -->
      <AiProcessingOverlay :visible="aiProcessingStore.processing" :text="aiProcessingStore.text"
        :fullscreen="false" />
    </div>
  </section>
</template>

<style scoped>
.manage-page { display: flex; flex-direction: column; gap: 12px; height: calc(100vh - 98px); font-size: 14px; }
/* 流程条 + 内容区的包裹层：AI 遮罩的定位父级，只覆盖这一块。 */
.manage-stage { position: relative; flex: 1; min-height: 0; display: flex; flex-direction: column; gap: 12px; }
.manage-stage.has-collapsed-flow { gap: 4px; }
.manage-flow-header { display: flex; align-items: center; justify-content: space-between; gap: 12px; flex-wrap: wrap;
  margin-bottom: 8px; padding-bottom: 8px; border-bottom: 1px dashed #d9dfe6; }
/* 处理中仍允许返回，其他流程操作继续由遮罩阻止。 */
.manage-heading { position: relative; z-index: 1001; display: flex; align-items: center; gap: 12px;
  flex: 1 1 320px; min-width: 0; pointer-events: none; }
.manage-back { flex: none; pointer-events: auto; }
.manage-title { flex: 0 1 auto; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
  font-weight: 700; font-size: 14px; color: #1b4168; }
.manage-flow { padding: 12px 16px 10px; background: var(--surface);
  border: 1px solid var(--line); border-radius: 10px; }
.flow-expand-row { display: flex; flex: none; align-items: center; justify-content: flex-end; min-height: 30px; }
.flow-expand { color: var(--brand, #1b64ac); }
.flow-steps { display: flex; align-items: center; margin: 0; padding: 0; list-style: none; }
.flow-step { display: flex; align-items: center; flex: 1 1 auto; min-width: 0; }
.flow-step:last-child { flex: none; }
.flow-step-node { display: inline-flex; align-items: center; justify-content: center; flex: none;
  width: 22px; height: 22px; border-radius: 50%; background: #f0f2f5; color: #a8abb2;
  font-size: 14px; font-weight: 600; }
.flow-step-title { margin-left: 7px; font-size: 14px; color: #909399; white-space: nowrap; }
.flow-step-line { flex: 1; height: 1px; margin: 0 10px; background: #e4e7ed; }
.flow-step.is-active .flow-step-node { background: var(--brand, #1b64ac); color: #fff; }
.flow-step.is-active .flow-step-title { color: var(--brand, #1b64ac); font-weight: 700; }
.flow-step.is-passed .flow-step-node { background: #e8f6ec; color: #34a853; }
.flow-step.is-passed .flow-step-title { color: #5a6472; }
.flow-step.is-clickable { cursor: pointer; }
.flow-step.is-clickable:hover .flow-step-node { background: var(--brand, #1b64ac); color: #fff; }
.flow-step.is-clickable:hover .flow-step-title { color: var(--brand, #1b64ac); }
.flow-step-line.is-done { background: #34a853; }
.manage-flow-actions { display: flex; align-items: center; justify-content: flex-end; gap: 8px; flex-wrap: wrap; }
.flow-toggle { flex: none; }
.manage-flow-actions :deep(.el-button) { font-size: 14px; }
.flow-locked-tip { color: var(--muted, #909399); font-size: 14px; }
.flow-error { color: #f56c6c; font-size: 14px; }
.manage-tabs { display: flex; flex: 1; flex-direction: column; min-height: 0; }
.manage-tabs :deep(.el-tabs__header) { flex: none; margin: 0; padding: 0 22px; background: #fff; }
.manage-tabs :deep(.el-tabs__item) { height: 42px; padding: 0 20px; font-size: 16px; font-weight: 500; }
.manage-tabs :deep(.el-tabs__item.is-active) { font-weight: 600; }
.manage-tabs :deep(.el-tabs__content) { flex: 1; min-height: 0; overflow: hidden; background: #f5f8fb; }
.manage-tabs :deep(.el-tab-pane) { height: 100%; min-height: 0; }
.manage-tab-label { display: inline-flex; align-items: center; gap: 6px; font-size: 16px; }
.manage-tab-icon { font-size: 18px; color: var(--el-color-primary); }
.manage-tab-badge { display: inline-flex; align-items: center; }
.manage-tab-badge :deep(.el-badge__content) { height: 16px; padding: 0 5px; font-size: 11px; line-height: 14px; font-weight: 400; }
.manage-tabs :deep(.el-button), .manage-tabs :deep(.el-input__inner),
.manage-tabs :deep(.el-select__placeholder), .manage-tabs :deep(.el-checkbox__label),
.manage-tabs :deep(.el-tag) { font-size: 14px; }
.manage-body { flex: 1; min-height: 0; overflow: hidden; display: flex; flex-direction: column; gap: 12px; }
.manage-stage-body { display: flex; flex-direction: column; height: 100%; min-height: 0; overflow: hidden; }
.manage-placeholder { flex: 1; display: flex; align-items: center; justify-content: center;
  background: var(--surface); border: 1px dashed var(--line); border-radius: 10px;
  color: var(--muted, #909399); font-size: 14px; }
@media (max-width: 800px) {
  .manage-tabs :deep(.el-tabs__header) { padding-inline: 12px; }
}
</style>
