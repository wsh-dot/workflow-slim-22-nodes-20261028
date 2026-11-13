<script setup lang="ts">
import { ref } from 'vue'
import PriceLibrary from './components/PriceLibrary.vue'
import HistoryLibrary from './components/HistoryLibrary.vue'
import RuleA06Panel from './components/RuleA06Panel.vue'

const activeTab = ref('case')
/** 规则库二级 tab：A-05 ~ A-11 规则（A-06 关联定额已实现，其余占位待建）。 */
const activeRuleTab = ref('a06')
</script>

<template>
  <section class="page-panel knowledge-page">
    <div class="page-header knowledge-header">
      <div class="page-title">知识库维护</div>
      <div class="page-subtitle">维护企业知识与价格数据</div>
    </div>
    <el-tabs v-model="activeTab" class="knowledge-tabs">
      <el-tab-pane label="历史案例库" name="case"><HistoryLibrary /></el-tab-pane>
      <el-tab-pane label="经验库" name="experience" />
      <el-tab-pane label="规则库" name="rule">
        <el-tabs v-model="activeRuleTab" class="rule-tabs">
          <el-tab-pane label="主材定额对应" name="a05">
            <div class="rule-tab-placeholder">A-05 主材-定额对应规则：原始主材与定额的对应关系，建设中</div>
          </el-tab-pane>
          <el-tab-pane label="关联定额" name="a06">
            <RuleA06Panel />
          </el-tab-pane>
          <el-tab-pane label="单位换算" name="a07">
            <div class="rule-tab-placeholder">A-07 单位换算规则：工程量单位换算，建设中</div>
          </el-tab-pane>
          <el-tab-pane label="说明书信息提取" name="a08">
            <div class="rule-tab-placeholder">A-08 说明书关键信息提取规则：各专业需从设计说明书提取的关键信息，建设中</div>
          </el-tab-pane>
          <el-tab-pane label="指标定额优先级" name="a09">
            <div class="rule-tab-placeholder">A-09 指标与定额优先级规则：各专业优先套用定额还是指标，建设中</div>
          </el-tab-pane>
          <el-tab-pane label="设备主材划分" name="a10">
            <div class="rule-tab-placeholder">A-10 设备主材划分规则：设备与主材的相互转换归类，建设中</div>
          </el-tab-pane>
          <el-tab-pane label="特征值对应" name="a11">
            <div class="rule-tab-placeholder">A-11 特征值对应关系规则：设备主材特征值与价格库特征值的对应，建设中</div>
          </el-tab-pane>
        </el-tabs>
      </el-tab-pane>
      <el-tab-pane label="价格库" name="price">
        <PriceLibrary />
      </el-tab-pane>
    </el-tabs>
  </section>
</template>

<style scoped>
.knowledge-page { height: calc(100vh - 124px); min-height: 540px; display: flex; flex-direction: column; overflow: hidden; }
.knowledge-header { flex: none; min-height: 48px; padding: 8px 22px; }
.knowledge-header .page-title { margin-right: 4px; }
.page-subtitle { color: #718296; font-size: var(--type-small); line-height: 1.5; }
.knowledge-tabs { flex: 1; min-height: 0; display: flex; flex-direction: column; }
.knowledge-tabs :deep(.el-tabs__header) { flex: none; margin: 0; padding: 0 22px; background: #fff; }
.knowledge-tabs :deep(.el-tabs__item) { height: 42px; padding: 0 20px; font-size: 15px; font-weight: 500; }
.knowledge-tabs :deep(.el-tabs__item.is-active) { font-weight: 600; }
.knowledge-tabs :deep(.el-tabs__content) { flex: 1; min-height: 0; background: #f5f8fb; }
.knowledge-tabs :deep(#pane-price) { height: 100%; min-height: 0; }
.knowledge-tabs :deep(#pane-rule) { height: 100%; min-height: 0; }
.knowledge-tabs :deep(#pane-case) { height: 100%; min-height: 0; }
/* 规则库二级 tab：铺满 pane，占位提示居中。 */
.rule-tabs { height: 100%; min-height: 0; display: flex; flex-direction: column; }
.rule-tabs :deep(.el-tabs__header) { flex: none; margin: 0; padding: 0 22px; background: #fff; }
.rule-tabs :deep(.el-tabs__item) { height: 38px; padding: 0 16px; font-size: 14px; font-weight: 500; }
.rule-tabs :deep(.el-tabs__item.is-active) { font-weight: 600; }
.rule-tabs :deep(.el-tabs__content) { flex: 1; min-height: 0; overflow: hidden; }
.rule-tab-placeholder { display: flex; align-items: center; justify-content: center; height: 100%;
  color: var(--muted, #909399); font-size: 13px; }
@media (max-width: 800px) {
  .knowledge-header { padding-inline: 16px; }
  .knowledge-tabs :deep(.el-tabs__header) { padding-inline: 12px; }
}
</style>
