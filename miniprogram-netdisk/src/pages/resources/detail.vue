<script setup lang="ts">
import { computed, ref } from "vue";
import { onLoad } from "@dcloudio/uni-app";
import { resources } from "@/data/mock";

const selectedId = ref("r1");
const resource = computed(() => resources.find((item) => item.id === selectedId.value) ?? resources[0]);
const unlocked = ref(Boolean(resource.value.unlocked));

onLoad((query) => {
  if (typeof query?.id === "string") {
    selectedId.value = query.id;
    unlocked.value = Boolean(resource.value.unlocked);
  }
});

const confirmAccess = () => {
  if (unlocked.value) return;
  uni.showModal({
    title: "确认获取资源？",
    content: `本资源需要消耗 ${resource.value.points} 积分，当前积分 100 分。`,
    confirmText: "确认获取",
    success: (res) => {
      if (res.confirm) unlocked.value = true;
    }
  });
};
</script>

<template>
  <view class="page">
    <view class="card">
      <view class="resource-title">{{ resource.title }}</view>
      <view class="row tag-line">
        <text class="tag">{{ resource.pan }}</text>
        <text class="tag tag-warning">{{ resource.level }}</text>
        <text class="tag">{{ resource.category }}</text>
      </view>
      <view class="price"><text class="points">{{ resource.points }}</text> 积分获取</view>
    </view>

    <view class="card section">
      <view class="section-title">资源简介</view>
      <view class="desc">{{ resource.description }}</view>
    </view>

    <view class="card section">
      <view class="info-line"><text>文件数量</text><text>{{ resource.files }}</text></view>
      <view class="info-line"><text>文件大小</text><text>{{ resource.size }}</text></view>
      <view class="info-line"><text>最近验证</text><text>{{ resource.verifiedAt }}</text></view>
      <view class="info-line"><text>获取次数</text><text>{{ resource.downloads }}</text></view>
      <view class="info-line"><text>收藏次数</text><text>{{ resource.favorites }}</text></view>
      <view class="info-line"><text>上传者</text><text>{{ resource.uploader }} · 信用{{ resource.credit }}</text></view>
    </view>

    <view class="card section secret-box">
      <view class="section-title">{{ unlocked ? "已解锁资源信息" : "解锁后可见" }}</view>
      <template v-if="unlocked">
        <view class="secret-line">链接：{{ resource.link }}</view>
        <view class="secret-line">提取码：{{ resource.extractCode || "无" }}</view>
        <view class="secret-line">解压码：{{ resource.unzipCode || "无" }}</view>
        <view class="btn-secondary btn copy-btn">复制链接</view>
      </template>
      <template v-else>
        <view class="masked">完整网盘链接、提取码、解压码将在消耗积分后展示。</view>
      </template>
    </view>

    <view class="bottom-actions">
      <view class="btn" @click="confirmAccess">{{ unlocked ? "已获取" : `获取资源 ${resource.points}分` }}</view>
      <view class="btn-plain">收藏</view>
      <view class="btn-plain danger">投诉失效</view>
    </view>
  </view>
</template>

<style lang="scss" scoped>
@import "@/styles/theme.scss";

.tag-line {
  gap: 10rpx;
  margin-top: 18rpx;
  flex-wrap: wrap;
}

.price {
  margin-top: 22rpx;
  font-size: 30rpx;
}

.desc {
  margin-top: 18rpx;
  color: $text-muted;
  font-size: 28rpx;
  line-height: 1.7;
}

.info-line {
  display: flex;
  justify-content: space-between;
  border-bottom: 1rpx solid $border;
  padding: 18rpx 0;
  color: $text-muted;
  font-size: 27rpx;
}

.info-line:last-child {
  border-bottom: 0;
}

.secret-box {
  margin-bottom: 144rpx;
}

.secret-line {
  margin-top: 16rpx;
  color: $text-main;
  font-size: 27rpx;
  line-height: 1.6;
}

.masked {
  margin-top: 18rpx;
  border: 1rpx dashed $border;
  border-radius: 12rpx;
  background: $tag-bg;
  padding: 24rpx;
  color: $text-muted;
  font-size: 27rpx;
  line-height: 1.6;
}

.copy-btn {
  margin-top: 22rpx;
}

.bottom-actions {
  position: fixed;
  right: 0;
  bottom: 0;
  left: 0;
  display: grid;
  grid-template-columns: 1.8fr 1fr 1fr;
  gap: 14rpx;
  border-top: 1rpx solid $border;
  background: #ffffff;
  padding: 18rpx 28rpx 30rpx;
}

.danger {
  color: $danger;
}
</style>
