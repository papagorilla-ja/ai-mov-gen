<template>
  <v-container fluid class="pa-0 editor-root-container" style="height: 100vh; display: flex; flex-direction: column;">
    <!-- ─── エディタトップヘッダー ─── -->
    <v-toolbar density="compact" class="glass-panel editor-top-bar px-2" color="transparent">
      <v-btn
        icon="mdi-arrow-left"
        variant="text"
        size="small"
        title="プロジェクト画面へ戻る"
        @click="$router.back()"
      />
      
      <div class="d-flex align-center gap-2 mr-4">
        <img :src="logoUrl" alt="Logo" class="editor-logo-img" />
        <div>
          <div class="text-subtitle-2 font-weight-bold editor-title text-truncate" style="max-width: 320px;">
            {{ videosStore.currentVideo?.name ?? '動画編集' }}
          </div>
        </div>
      </div>

      <div class="d-flex align-center gap-2">
        <!-- 動画ステータスバッジ -->
        <v-chip
          :color="statusColor(videosStore.currentVideo?.status)"
          size="x-small"
          class="font-weight-bold text-uppercase px-2"
          variant="flat"
        >
          <span v-if="videosStore.currentVideo?.status === 'generating'" class="status-pulse-dot mr-1"></span>
          {{ videosStore.currentVideo?.status ?? 'draft' }}
        </v-chip>

        <!-- 再生時間バッジ -->
        <v-chip size="x-small" variant="tonal" color="info" v-if="videosStore.currentVideo?.duration_sec">
          <v-icon size="12" class="mr-1">mdi-timer-outline</v-icon>
          {{ videosStore.currentVideo.duration_sec.toFixed(1) }}s
        </v-chip>
      </div>

      <v-spacer />

      <!-- ヘッダークイックガイド -->
      <div class="text-caption text-medium-emphasis mr-2 d-none d-md-flex align-center">
        <v-icon size="14" color="#06b6d4" class="mr-1">mdi-movie-edit-outline</v-icon>
        Studio Timeline Editor
      </div>
    </v-toolbar>

    <!-- ─── 制作ワークフロー・ステッパータブ ─── -->
    <v-tabs v-model="activeTab" class="editor-stepper-tabs glass-panel" bg-color="transparent" density="comfortable" color="primary">
      <v-tab value="scenario" class="stepper-tab">
        <span class="step-num">1</span>
        <v-icon size="16" class="mr-1">mdi-script-text-outline</v-icon>
        <span>シナリオ作成</span>
      </v-tab>
      <v-tab value="scenes" class="stepper-tab">
        <span class="step-num">2</span>
        <v-icon size="16" class="mr-1">mdi-view-carousel-outline</v-icon>
        <span>シーン編集</span>
      </v-tab>
      <v-tab value="speaker" class="stepper-tab">
        <span class="step-num">3</span>
        <v-icon size="16" class="mr-1">mdi-microphone-outline</v-icon>
        <span>話者設定</span>
      </v-tab>
      <v-tab value="style" class="stepper-tab">
        <span class="step-num">4</span>
        <v-icon size="16" class="mr-1">mdi-palette-outline</v-icon>
        <span>デザインスタイル</span>
      </v-tab>
      <v-tab value="output" class="stepper-tab">
        <span class="step-num">5</span>
        <v-icon size="16" class="mr-1">mdi-movie-play-outline</v-icon>
        <span>動画レンダリング出力</span>
      </v-tab>
    </v-tabs>

    <!-- タブコンテンツ -->
    <v-window v-model="activeTab" style="flex: 1; overflow-y: auto;">
      <!-- シナリオタブ -->
      <v-window-item value="scenario">
        <v-container class="pa-6" max-width="960">
          <div class="mb-6 text-center">
            <h2 class="text-h6 font-weight-bold mb-2">動画シナリオの作成・生成</h2>
            <p class="text-body-2 text-medium-emphasis">動画のシナリオを作成・解析する方法を以下から選択してください。</p>
            
            <v-btn-toggle
              v-model="scenarioRoute"
              mandatory
              color="primary"
              variant="outlined"
              class="mt-4 glass-card"
            >
              <v-btn value="pptx" prepend-icon="mdi-presentation">PPTXから取り込む</v-btn>
              <v-btn value="text" prepend-icon="mdi-text-box-plus-outline">テキスト貼り付け</v-btn>
              <v-btn value="chat" prepend-icon="mdi-chat-processing-outline">AIチャットで作成</v-btn>
            </v-btn-toggle>
          </div>

          <!-- 各ルートのコンポーネント -->
          <v-card class="mb-6 glass-card overflow-hidden">
            <ScenarioRouteA v-if="scenarioRoute === 'pptx'" :video-id="videoId" @finalized="onScenarioFinalized" />
            <ScenarioRouteB v-if="scenarioRoute === 'text'" :video-id="videoId" @finalized="onScenarioFinalized" />
            <ScenarioRouteC v-if="scenarioRoute === 'chat'" :video-id="videoId" @finalized="onScenarioFinalized" />
          </v-card>

          <!-- 確定済みの現在のシナリオ（シーン一覧） -->
          <v-card class="pa-4 glass-card">
            <div class="d-flex align-center justify-between mb-4">
              <span class="text-subtitle-1 font-weight-bold">🎬 現在のシーン構成 ({{ scenesStore.scenes.length }})</span>
              <v-spacer />
              <v-btn
                prepend-icon="mdi-playlist-edit"
                size="small"
                color="secondary"
                variant="outlined"
                @click="activeTab = 'scenes'"
              >
                詳細エディタで編集する
              </v-btn>
            </div>
            
            <v-list class="bg-transparent" v-if="scenesStore.scenes.length">
              <v-card
                v-for="element in scenesStore.scenes"
                :key="element.id"
                variant="outlined"
                class="mb-2 glass-card border-thin"
              >
                <v-card-text class="pa-3 d-flex align-center">
                  <div class="flex-grow-1 text-truncate">
                    <div class="d-flex align-center gap-2 mb-1">
                      <span class="text-caption font-weight-bold text-primary">Scene {{ element.index }}</span>
                      <v-chip size="x-small" variant="tonal">{{ element.layout_type }}</v-chip>
                    </div>
                    <div class="text-body-2 font-weight-bold text-truncate">{{ element.title || '無題のシーン' }}</div>
                    <div class="text-caption text-medium-emphasis text-truncate">{{ element.narration_text || element.outline_summary || 'あらすじ未設定' }}</div>
                  </div>
                  <v-btn icon="mdi-delete-outline" color="error" variant="text" size="small" @click.stop="handleDeleteScene(element.id)" />
                </v-card-text>
              </v-card>
            </v-list>
            <div v-else class="text-center py-8 text-medium-emphasis text-caption">
              現在、シーンはありません。上のいずれかの方法でシナリオを作成・生成してください。
            </div>
          </v-card>
        </v-container>
      </v-window-item>

      <!-- シーンタブ -->
      <v-window-item value="scenes" style="height: 100%;">
        <v-row no-gutters style="height: 100%;">
          <!-- 左側: シーン一覧 (タイムライン) -->
          <v-col cols="12" md="4" class="border-e d-flex flex-column cyber-scenes-col" style="height: 100%; max-height: calc(100vh - 112px);">
            <div class="pa-3 border-b d-flex justify-between align-center flex-wrap gap-2 glass-panel">
              <span class="text-subtitle-2 font-weight-bold d-flex align-center gap-1">
                <v-icon size="16" color="#06b6d4">mdi-view-sequential-outline</v-icon>
                シーン構成 ({{ scenesStore.scenes.length }})
              </span>
              <v-spacer />
              <v-btn
                prepend-icon="mdi-auto-fix"
                size="small"
                class="btn-neon-ai mr-2"
                :loading="scenesStore.bulkGenLoading"
                :disabled="!scenesStore.scenes.length"
                @click="handleGenerateAllContent"
              >
                ✨ AIで全生成
              </v-btn>
              <v-btn prepend-icon="mdi-plus" size="small" color="primary" variant="tonal" @click="handleAddScene">
                追加
              </v-btn>
            </div>
            
            <div class="overflow-y-auto flex-grow-1 pa-2 cyber-scenes-list-container">
              <v-list class="bg-transparent" v-if="scenesStore.scenes.length">
                <!-- ドラッグ＆ドロップ -->
                <draggable
                  v-model="scenesStore.scenes"
                  item-key="id"
                  handle=".drag-handle"
                  @end="onDragEnd"
                  class="v-list"
                >
                  <template #item="{ element, index }">
                    <v-card
                      :color="selectedScene?.id === element.id ? 'primary' : 'transparent'"
                      variant="flat"
                      class="mb-2 drag-item glass-card"
                      @click="selectScene(element)"
                    >
                      <v-card-text class="pa-2 d-flex align-center gap-2">
                        <v-icon class="drag-handle cursor-grab flex-shrink-0" color="medium-emphasis" size="18">mdi-drag</v-icon>

                        <!-- ミニサムネイル -->
                        <div class="scene-thumb rounded flex-shrink-0" :class="`thumb-${element.layout_type}`">
                          <v-icon size="16" color="white">{{ layoutIcon(element.layout_type) }}</v-icon>
                        </div>

                        <!-- テキスト情報 -->
                        <div class="flex-grow-1 min-width-0">
                          <div class="d-flex align-center gap-1 mb-1">
                            <span class="text-caption text-medium-emphasis">{{ element.index }}</span>
                            <v-chip
                              :color="layoutColor(element.layout_type)"
                              size="x-small"
                              label
                              variant="flat"
                              class="px-1"
                              style="font-size: 9px; height: 16px;"
                            >
                              {{ layoutLabel(element.layout_type) }}
                            </v-chip>
                          </div>
                          <div class="text-body-2 font-weight-bold text-truncate">{{ element.title || '無題のシーン' }}</div>
                          <div class="text-caption text-medium-emphasis text-truncate">
                            {{ element.narration_text
                                ? element.narration_text.slice(0, 35) + (element.narration_text.length > 35 ? '…' : '')
                                : 'ナレーション未入力' }}
                          </div>
                        </div>

                        <!-- 操作ボタン -->
                        <div class="d-flex flex-column align-center flex-shrink-0">
                          <v-btn icon="mdi-chevron-up" variant="text" density="compact" size="small"
                            :disabled="index === 0" @click.stop="moveIndex(element, index, -1)" />
                          <v-btn icon="mdi-chevron-down" variant="text" density="compact" size="small"
                            :disabled="index === scenesStore.scenes.length - 1" @click.stop="moveIndex(element, index, 1)" />
                        </div>
                        <v-btn icon="mdi-delete-outline" color="error" variant="text" size="small"
                          @click.stop="handleDeleteScene(element.id)" />
                      </v-card-text>
                    </v-card>
                  </template>
                </draggable>
              </v-list>
              <div v-else class="text-center py-16 text-medium-emphasis">
                シーンがありません。追加ボタンから作成してください。
              </div>
            </div>
          </v-col>

          <!-- 右側: シーン詳細編集 -->
          <v-col cols="12" md="8" class="pa-6 overflow-y-auto" style="height: 100%; max-height: calc(100vh - 112px);">
            <div v-if="selectedScene" class="d-flex flex-column gap-4">
              <div class="d-flex align-center mb-2">
                <span class="text-h6 font-weight-bold">シーン詳細 (Scene {{ selectedScene.index }})</span>
                <v-spacer />
                <v-btn prepend-icon="mdi-volume-high" color="secondary" variant="outlined" class="mr-2" :loading="previewLoading" @click="handlePlayPreview">
                  プレビュー再生
                </v-btn>
                <v-btn prepend-icon="mdi-content-save" color="success" :loading="saveLoading" @click="handleSaveScene">
                  保存
                </v-btn>
              </div>
              <!-- 処理中インジケーター -->
              <div v-if="processingLabel" class="d-flex align-center gap-2 mb-3 text-body-2 text-medium-emphasis">
                <v-progress-circular size="14" width="2" indeterminate color="primary" />
                <span>{{ processingLabel }}</span>
              </div>
              <!-- プレビュー音声プレイヤー -->
              <v-card v-if="scenesStore.previewAudioUrl && !previewLoading" class="pa-3 mb-3 d-flex align-center gap-4 border-primary border-opacity-50" rounded style="background: rgba(var(--v-theme-primary), 0.05); border: 1px solid rgb(var(--v-theme-primary));">
                <div class="d-flex flex-column">
                  <span class="text-caption font-weight-bold text-primary">生成されたプレビュー音声</span>
                  <span class="text-caption text-medium-emphasis" v-if="previewAudioDuration">長さ: {{ previewAudioDuration.toFixed(1) }} 秒</span>
                </div>
                <audio
                  :src="scenesStore.previewAudioUrl"
                  ref="previewAudioPlayer"
                  controls
                  autoplay
                  style="height: 32px;"
                  @loadedmetadata="handleAudioLoaded"
                />
              </v-card>
              <!-- プレビューエラー (手動で閉じるまで消えない永続表示) -->
              <v-alert
                v-if="previewError"
                type="error"
                variant="tonal"
                closable
                class="mb-3 text-body-2"
                @click:close="previewError = null"
              >
                <div class="font-weight-bold mb-1">プレビュー音声の生成に失敗しました</div>
                <div style="white-space: pre-wrap; word-break: break-all;">{{ previewError }}</div>
              </v-alert>

              <v-card class="pa-4 mb-4 glass-card">
                <v-card-title class="pa-0 mb-4 text-subtitle-1 font-weight-bold">基本情報</v-card-title>
                <v-text-field v-model="editForm.title" label="シーンタイトル" class="mb-3" />
                <v-textarea
                  v-if="editForm.outline_summary"
                  v-model="editForm.outline_summary"
                  label="あらすじ（意図）"
                  rows="2"
                  readonly
                  hint="チャット等で作成されたこのシーンのあらすじ"
                  persistent-hint
                  class="mb-3"
                />
                <!-- レイアウトは 40 種規模になるため、名前のドロップダウンでは選べない。
                     型でまとめたギャラリーから、実物のサムネイルを見て選ぶ。 -->
                <div class="mb-3">
                  <div class="text-caption text-medium-emphasis mb-1">レイアウト</div>
                  <v-btn
                    block variant="outlined" class="justify-start"
                    :prepend-icon="layoutIcon(editForm.layout_type)"
                    append-icon="mdi-view-grid-plus-outline"
                    @click="layoutPickerOpen = true"
                  >
                    <span class="text-body-2">{{ layoutLabel(editForm.layout_type) }}</span>
                    <v-chip size="x-small" variant="tonal" class="ml-2">
                      {{ currentTypeDef?.label || '' }}
                    </v-chip>
                  </v-btn>
                  <div class="text-caption text-medium-emphasis mt-1">
                    {{ currentLayoutDef?.when_to_use || '' }}
                  </div>
                </div>
                <LayoutPicker
                  v-model:open="layoutPickerOpen"
                  v-model="editForm.layout_type"
                  :item-count="currentItemCount"
                  :video-id="videoId"
                  @select="handleLayoutSelected"
                />
                <v-select
                  v-model="editForm.speaker_id"
                  :items="speakerOptions"
                  label="話者オーバーライド"
                  hint="動画のデフォルト話者と異なる話者を使用する場合のみ設定してください。"
                  persistent-hint
                />
                <v-select
                  v-if="editForm.layout_type === 'chat_dialog'"
                  v-model="editForm.speaker_b_id"
                  :items="speakerOptions"
                  label="話者 B (対話の B 役)"
                  hint="chat_dialog レイアウトで B ラベルの行を担当する話者。未設定の場合は話者 A と同じ声になります。"
                  persistent-hint
                  class="mt-3"
                />
              </v-card>

              <v-alert
                v-if="isDummySpeakerSelected"
                type="warning"
                variant="tonal"
                density="compact"
                class="mb-4 text-caption"
                icon="mdi-alert-circle-outline"
              >
                選択中の話者はダミー音声です。プレビューや合成は無音になります。実用的な合成には設定画面からオリジナル話者を登録してください。
              </v-alert>

              <v-card class="pa-4 mb-4 glass-card">
                <div class="d-flex align-center justify-between mb-4">
                  <v-card-title class="pa-0 text-subtitle-1 font-weight-bold">スライド表示テキスト</v-card-title>
                  <v-btn
                    prepend-icon="mdi-auto-fix"
                    size="small"
                    color="secondary"
                    variant="outlined"
                    :loading="contentGenLoading"
                    @click="generateSceneContent"
                  >
                    AI でシーン内容を生成
                  </v-btn>
                </div>
                <!-- 入力欄はレイアウトごとに書かない。型のスキーマ（/api/v1/layouts）から
                     自動生成する。レイアウトを足してもこの画面は変更不要。 -->
                <SceneContentForm
                  v-model="slideContent"
                  :type-def="currentTypeDef"
                  :field-notes="currentLayoutDef?.field_notes || {}"
                />

                <v-textarea
                  v-if="slideContent.image_prompt_note"
                  v-model="slideContent.image_prompt_note"
                  label="画像の狙い（AI の補足）"
                  rows="2" readonly persistent-hint
                  hint="画像生成 AI に渡した意図の控え"
                  class="mb-3"
                />
              </v-card>

              <v-card class="pa-4 glass-card">
                <div class="d-flex align-center justify-between mb-2">
                  <v-card-title class="pa-0 text-subtitle-1 font-weight-bold">ナレーション</v-card-title>
                  <v-btn
                    prepend-icon="mdi-robot-outline"
                    size="small"
                    color="secondary"
                    variant="outlined"
                    :loading="narrationGenLoading"
                    @click="generateNarration"
                  >
                    AI でナレーションを生成
                  </v-btn>
                </div>

                <v-textarea
                  v-model="editForm.narration_text"
                  label="ナレーションテキスト"
                  rows="5"
                  class="mb-2"
                />
                <div class="d-flex align-center justify-between text-caption mt-1">
                  <span class="text-medium-emphasis">
                    {{ editForm.narration_text?.length ?? 0 }} 文字 &nbsp;/&nbsp; 約 {{ estimatedDuration }} 秒
                  </span>
                  <v-chip
                    :color="narrationChipColor"
                    size="x-small"
                    label
                    variant="tonal"
                  >
                    {{ narrationLengthHint }}
                  </v-chip>
                </div>
              </v-card>

              <!-- ── AI デザイン調整 ── -->
              <v-card class="mb-4 glass-card border-thin" variant="outlined">
                <v-card-title class="text-body-2 font-weight-bold pa-3 pb-0">AI デザイン調整</v-card-title>
                <v-card-text class="pa-3">
                  <div class="d-flex gap-2 align-center">
                    <v-text-field v-model="designPrompt" placeholder="例: グラフをもっと大きく、背景に光の演出を追加して" hide-details density="compact" />
                    <v-btn color="secondary" :loading="applyingDesign" @click="applyDesignAdjust">AI で調整</v-btn>
                  </div>
                  <div v-if="selectedScene?.custom_html" class="text-caption text-medium-emphasis mt-2 d-flex align-center">
                    <v-icon size="14" class="mr-1">mdi-pencil</v-icon> このシーンはカスタムコードで上書きされています
                    <v-spacer />
                    <v-btn size="x-small" variant="text" color="warning" @click="resetSceneCustomCode">自動生成に戻す</v-btn>
                  </div>
                </v-card-text>
              </v-card>

              <!-- ── コードを表示・編集 ── -->
              <v-card class="mb-4 glass-card border-thin" variant="outlined">
                <v-card-title class="text-body-2 font-weight-bold pa-3 pb-0 d-flex align-center">
                  コードを表示・編集
                  <v-spacer />
                  <v-btn size="small" variant="text" @click="loadSceneCode">読み込み</v-btn>
                  <v-btn size="small" variant="text" @click="codeEditMode = !codeEditMode">
                    {{ codeEditMode ? '編集中' : '編集する' }}
                  </v-btn>
                </v-card-title>
                <v-card-text class="pa-3">
                  <v-textarea v-model="codeHtml" label="HTML" rows="6" class="font-mono" :readonly="!codeEditMode" density="compact" />
                  <v-textarea v-model="codeCss" label="CSS (このシーン専用、任意)" rows="4" class="font-mono" :readonly="!codeEditMode" density="compact" />
                  <div class="d-flex gap-2">
                    <v-btn size="small" color="primary" :disabled="!codeEditMode" @click="applySceneCode">適用</v-btn>
                    <v-btn size="small" variant="outlined" @click="refreshCodePreview">プレビューを更新</v-btn>
                  </div>
                  <iframe v-if="codePreviewUrl" :src="codePreviewUrl" style="width:100%; height:360px; border:1px solid rgba(255,255,255,0.1); margin-top:12px; border-radius:8px;" />
                </v-card-text>
              </v-card>
              <v-card class="pa-4 mb-4 glass-card">
                <div class="d-flex align-center justify-between mb-2">
                  <v-card-title class="pa-0 text-subtitle-1 font-weight-bold">画像生成プロンプト</v-card-title>
                  <v-btn prepend-icon="mdi-image-plus" size="small" color="secondary" variant="outlined"
                         :loading="imagePromptLoading" @click="generateImagePrompt">
                    AI でプロンプトを生成
                  </v-btn>
                </div>
                <div class="text-caption text-medium-emphasis mb-3">
                  生成したプロンプトを Gemini などの画像生成AIに貼り付け、できた画像を下の「アセット」から
                  アップロードするとスライドに反映されます。
                </div>

                <template v-if="selectedScene?.image_prompt">
                  <v-textarea :model-value="selectedScene.image_prompt" readonly rows="4"
                              class="font-mono mb-2" density="compact" hide-details />
                  <div class="d-flex align-center gap-2">
                    <v-btn size="small" color="primary" prepend-icon="mdi-content-copy" @click="copyImagePrompt">
                      プロンプトをコピー
                    </v-btn>
                    <span v-if="slideContent.image_prompt_note" class="text-caption text-medium-emphasis">
                      {{ slideContent.image_prompt_note }}
                    </span>
                  </div>
                </template>
                <div v-else class="text-caption text-medium-emphasis py-2">
                  まだ生成されていません。「AI でプロンプトを生成」を押してください。
                </div>
              </v-card>

              <!-- 画像の取り込み口はここ 1 か所。枚数はレイアウトの capacity が決める。 -->
              <SceneAssetSlot
                v-if="selectedScene"
                :scene-id="selectedScene.id"
                :slot-count="assetSlotCount"
                :show-captions="isMediaLayout"
                :captions="slotCaptions"
                @update:captions="applySlotCaptions"
              />
            </div>
            <div v-else class="text-center py-16 text-medium-emphasis">
              左側のシーン一覧から編集するシーンを選択してください。
            </div>
          </v-col>
        </v-row>
      </v-window-item>

      <!-- 話者タブ -->
      <v-window-item value="speaker">
        <v-container class="pa-6" max-width="600">
          <v-card class="pa-4 glass-card">
            <v-card-title class="font-weight-bold">動画デフォルト話者</v-card-title>
            <v-card-text class="pt-4">
              <p class="text-body-2 text-medium-emphasis mb-4">動画全体で標準として使用するナレーター話者を選択します。</p>
              <v-select
                v-model="defaultSpeakerId"
                :items="speakerOptions.filter(o => o.value !== null)"
                label="デフォルト話者"
                class="mb-4"
              />
              <v-select
                v-model="defaultSpeakerBId"
                :items="speakerOptions.filter(o => o.value !== null)"
                label="デフォルト話者 B (chat_dialog 用)"
                hint="chat_dialog シーンの B 役に使用するデフォルト話者。シーン個別設定が優先されます。"
                persistent-hint
                class="mb-4"
              />
              <v-btn color="primary" @click="handleSaveSpeaker">デフォルト話者を保存</v-btn>
            </v-card-text>
          </v-card>
        </v-container>
      </v-window-item>

      <!-- スタイルタブ -->
      <v-window-item value="style">
        <StyleConfigTab :video-id="videoId" />
      </v-window-item>

      <!-- 出力タブ -->
      <v-window-item value="output">
        <v-container class="pa-6">
          <!-- 生成ステータス -->
          <v-card class="pa-6 mb-6 glass-card">
            <div class="d-flex align-center mb-4">
              <div>
                <h3 class="text-h6 font-weight-bold">動画の生成</h3>
                <p class="text-body-2 text-medium-emphasis">シーン音声の合成、タイムライン計算、動画レンダリングを一括実行します。</p>
              </div>
              <v-spacer />
              <v-btn
                color="secondary"
                size="large"
                prepend-icon="mdi-monitor-eye"
                variant="outlined"
                class="mr-3"
                :loading="slidePreviewLoading"
                @click="handleSlidePreview"
              >
                スライドプレビュー
              </v-btn>
              <v-btn
                v-if="videosStore.currentVideo?.status === 'generating' || generationStore.currentProgress?.step === 'generating'"
                color="warning"
                size="large"
                prepend-icon="mdi-refresh"
                variant="tonal"
                class="mr-3"
                :loading="generationStore.loading"
                @click="handleResetStatus"
              >
                ステータスを強制リセット
              </v-btn>
              <v-btn
                color="primary"
                size="large"
                prepend-icon="mdi-play-circle"
                :disabled="videosStore.currentVideo?.status === 'generating'"
                @click="openGenerateDialog"
              >
                動画を生成
              </v-btn>
            </div>

            <!-- 生成オプションダイアログ -->
            <v-dialog v-model="generateDialog" max-width="520">
              <v-card class="glass-card">
                <v-card-title class="pa-4 text-h6">動画の生成</v-card-title>
                <v-card-text class="pa-4 pt-0">
                  <v-checkbox
                    v-model="generateOptions.regenerateAudio"
                    color="primary"
                    hide-details
                    label="音声を再作成する"
                  />
                  <div class="text-caption text-medium-emphasis mt-1 ml-8">
                    既存のナレーション音声を削除してから合成し直します。
                    話者を変更した場合や、同じ話者の参照音声を録り直した場合に指定してください。
                    <br />
                    チェックしない場合は、内容が変わっていないシーンの音声を再利用して高速に生成します。
                  </div>
                  <v-alert
                    v-if="generateOptions.regenerateAudio"
                    type="info"
                    variant="tonal"
                    density="compact"
                    class="mt-3 text-caption"
                  >
                    全シーンの音声を合成し直すため、生成に時間がかかります。
                  </v-alert>
                </v-card-text>
                <v-card-actions class="pa-4 d-flex justify-end">
                  <v-btn variant="text" @click="generateDialog = false">キャンセル</v-btn>
                  <v-btn color="primary" :loading="generationStore.loading" @click="handleGenerate">
                    生成を開始
                  </v-btn>
                </v-card-actions>
              </v-card>
            </v-dialog>

            <!-- 進捗表示 -->
            <div v-if="generationStore.currentProgress" class="mt-4 border-t pt-4">
              <div class="d-flex align-center mb-2">
                <span
                  class="text-subtitle-2 font-weight-bold text-uppercase"
                  :class="(generationStore.currentProgress.error || generationStore.currentProgress.step === 'failed') ? 'text-error' : ''"
                >
                  ステータス: {{ (generationStore.currentProgress.error || generationStore.currentProgress.step === 'failed') ? 'エラー' : generationStore.currentProgress.step }}
                </span>
                <v-spacer />
                <span class="text-caption text-medium-emphasis">
                  {{ (generationStore.currentProgress.progress * 100).toFixed(0) }}%
                </span>
              </div>
              <v-progress-linear
                :model-value="generationStore.currentProgress.progress * 100"
                :color="(generationStore.currentProgress.error || generationStore.currentProgress.step === 'failed') ? 'error' : 'primary'"
                height="10"
                :striped="videosStore.currentVideo?.status === 'generating' && generationStore.currentProgress?.progress < 1.0 && !generationStore.currentProgress?.error && generationStore.currentProgress?.step !== 'failed'"
                rounded
              />
              <v-alert
                v-if="generationStore.currentProgress.error || generationStore.currentProgress.step === 'failed'"
                type="error"
                variant="tonal"
                class="mt-3"
                density="compact"
              >
                {{ generationStore.currentProgress.error || generationStore.currentProgress.message || '動画生成中にエラーが発生しました。' }}
              </v-alert>
              <v-alert
                v-else-if="videosStore.currentVideo?.status === 'completed' || (generationStore.currentProgress.step === 'rendering' && generationStore.currentProgress.progress === 1.0)"
                type="success"
                variant="tonal"
                class="mt-3"
                density="compact"
              >
                動画の生成が正常に完了しました！生成履歴からプレビュー・再生できます。
              </v-alert>
              <p v-else class="text-body-2 mt-2 text-medium-emphasis">
                {{ generationStore.currentProgress.message }}
              </p>
            </div>
          </v-card>

          <!-- 履歴 -->
          <v-card class="pa-4 glass-card">
            <v-card-title class="font-weight-bold px-2 mb-4">生成履歴</v-card-title>
            <v-table v-if="generationStore.histories.length">
              <thead>
                <tr>
                  <th>サムネイル</th>
                  <th>開始時間</th>
                  <th>ステータス</th>
                  <th>動画尺</th>
                  <th>ファイルサイズ</th>
                  <th class="text-right">アクション</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="h in generationStore.histories" :key="h.id">
                  <td style="width: 80px;">
                    <img
                      v-if="h.thumbnail_path"
                      :src="`/${h.thumbnail_path}`"
                      style="width: 72px; height: 40px; object-fit: cover; border-radius: 4px;"
                      :alt="`thumbnail-${h.id}`"
                    />
                    <div
                      v-else
                      style="width: 72px; height: 40px; background: rgba(128,128,128,0.2); border-radius: 4px; display: flex; align-items: center; justify-content: center;"
                    >
                      <v-icon size="18" color="grey">mdi-image-off</v-icon>
                    </div>
                  </td>
                  <td>{{ formatDate(h.started_at) }}</td>
                  <td>
                    <v-chip :color="statusColor(h.status)" size="x-small" class="text-uppercase font-weight-bold">
                      {{ h.status }}
                    </v-chip>
                  </td>
                  <td>{{ h.duration_sec ? `${h.duration_sec.toFixed(1)} 秒` : '-' }}</td>
                  <td>{{ h.file_size_bytes ? formatBytes(h.file_size_bytes) : '-' }}</td>
                  <td class="text-right">
                    <v-btn
                      v-if="h.status === 'completed'"
                      prepend-icon="mdi-play-circle"
                      color="primary"
                      variant="outlined"
                      size="small"
                      class="mr-2"
                      @click="openVideoPlayer(h.id)"
                    >
                      再生
                    </v-btn>
                    <v-btn
                      v-if="h.status === 'completed'"
                      prepend-icon="mdi-download"
                      color="success"
                      variant="flat"
                      size="small"
                      :href="generationStore.downloadUrl(h.id)"
                      target="_blank"
                    >
                      ダウンロード
                    </v-btn>
                    <v-btn
                      v-if="h.status === 'completed'"
                      prepend-icon="mdi-subtitles-outline"
                      color="secondary"
                      variant="outlined"
                      size="small"
                      class="ml-2"
                      :href="`/api/v1/generations/${h.id}/subtitle.srt`"
                      target="_blank"
                    >
                      字幕 SRT
                    </v-btn>
                    <v-btn
                      v-if="h.status === 'running'"
                      icon="mdi-refresh"
                      color="warning"
                      variant="text"
                      size="small"
                      title="ステータスをリセット"
                      class="ml-2"
                      @click="handleResetStatus"
                    />
                    <v-btn
                      v-if="h.status !== 'running'"
                      icon="mdi-delete-outline"
                      color="error"
                      variant="text"
                      size="small"
                      class="ml-2"
                      @click="confirmDeleteHistory(h)"
                    />
                  </td>
                </tr>
              </tbody>
            </v-table>
            <div v-else class="text-center py-8 text-medium-emphasis">
              生成履歴がありません。
            </div>
          </v-card>
        </v-container>
        <!-- インアプリ動画プレイヤー -->
        <v-dialog v-model="playerDialog" max-width="960" @after-leave="playerSrc = ''">
          <v-card>
            <v-card-title class="d-flex align-center pa-4">
              <v-icon class="mr-2">mdi-play-circle</v-icon>
              動画プレビュー
              <v-spacer />
              <v-btn icon="mdi-close" variant="text" @click="playerDialog = false" />
            </v-card-title>
            <v-divider />
            <v-card-text class="pa-0 bg-black">
              <video
                v-if="playerSrc"
                :src="playerSrc"
                controls
                autoplay
                style="width: 100%; max-height: 70vh; display: block;"
              />
            </v-card-text>
          </v-card>
        </v-dialog>
        <!-- スライド HTML プレビュー -->
        <v-dialog
          v-model="slidePreviewDialog"
          max-width="1100"
          @after-leave="slidePreviewUrl = ''"
        >
          <v-card>
            <v-card-title class="d-flex align-center pa-4">
              <v-icon class="mr-2">mdi-monitor-eye</v-icon>
              スライドプレビュー
              <v-spacer />
              <v-btn icon="mdi-close" variant="text" @click="slidePreviewDialog = false" />
            </v-card-title>
            <v-divider />
            <v-card-text class="pa-0" style="background: #000;">
              <iframe
                v-if="slidePreviewUrl"
                :src="slidePreviewUrl"
                style="width: 100%; aspect-ratio: 16/9; border: none; display: block;"
                title="スライドプレビュー"
              />
            </v-card-text>
            <v-card-actions class="pa-3">
              <span class="text-caption text-medium-emphasis">
                ※ 音声未合成のシーンは無音で表示されます。スライドのレイアウトと文字を確認するためのものです。
              </span>
              <v-spacer />
              <v-btn size="small" variant="text" @click="slidePreviewDialog = false">閉じる</v-btn>
            </v-card-actions>
          </v-card>
        </v-dialog>
      </v-window-item>
    </v-window>
  </v-container>
</template>

<script setup>
import { ref, reactive, onMounted, onBeforeUnmount, watch, computed } from 'vue'
import { useRoute } from 'vue-router'
import draggable from 'vuedraggable'
import { useVideosStore } from '@/stores/videos'
import { useScenesStore } from '@/stores/scenes'
import { useSpeakersStore } from '@/stores/speakers'
import { useGenerationStore } from '@/stores/generation'
import StyleConfigTab from '@/components/StyleConfigTab.vue'
import SceneAssetSlot from '@/components/SceneAssetSlot.vue'

import ScenarioRouteA from '@/components/ScenarioRouteA.vue'
import ScenarioRouteB from '@/components/ScenarioRouteB.vue'
import ScenarioRouteC from '@/components/ScenarioRouteC.vue'
import { useScenarioStore } from '@/stores/scenario'
import { scenarioApi } from '@/api/scenario'
import LayoutPicker from '@/components/LayoutPicker.vue'
import SceneContentForm from '@/components/SceneContentForm.vue'
import { useLayoutsStore } from '@/stores/layouts'
import { layoutApi } from '@/api/layout'
import { useUiStore } from '@/stores/ui'
import { api } from '@/api/index.js'
import logoUrl from '@/assets/logo.jpg'

const route = useRoute()
const videoId = route.params.videoId

const videosStore = useVideosStore()
const scenesStore = useScenesStore()
const speakersStore = useSpeakersStore()
const generationStore = useGenerationStore()
const scenarioStore = useScenarioStore()
const ui = useUiStore()

const activeTab = ref('scenes')
const selectedScene = ref(null)
const previewLoading = ref(false)
const previewError = ref(null)
const previewElapsedSec = ref(0)
const previewAudioDuration = ref(0)
const previewAudioPlayer = ref(null)
const playerDialog = ref(false)
const playerSrc = ref('')
const saveLoading = ref(false)
// 動画生成の実行オプション
const generateDialog = ref(false)
const generateOptions = reactive({ regenerateAudio: false })
const defaultSpeakerId = ref(null)
const defaultSpeakerBId = ref(null)
const slidePreviewDialog = ref(false)
const slidePreviewUrl = ref('')
const slidePreviewLoading = ref(false)

const scenarioRoute = ref('pptx')
const narrationGenLoading = ref(false)
const contentGenLoading = ref(false)

const designPrompt = ref('')
const applyingDesign = ref(false)
const codeEditMode = ref(false)
const codeHtml = ref('')
const codeCss = ref('')
const codePreviewUrl = ref('')

const imagePromptLoading = ref(false)
const rawSlideContent = ref({})

const editForm = reactive({
  title: '',
  layout_type: 'text_only',
  narration_text: '',
  outline_summary: '',
  speaker_id: null,
  speaker_b_id: null
})

// スライドの内容。型のスキーマに沿った形（/api/v1/layouts が配る定義と対）で、
// バックエンドが normalize 済みのものをそのまま持つ。
// 以前はレイアウト別のフラットな項目（left_title, chartLabels …）を平置きしていたが、
// レイアウトが増えるたびにここへ項目を足す必要があり、
// レイアウトを切り替えると入力が消える原因にもなっていた。
const slideContent = ref({})
const layoutPickerOpen = ref(false)

const layoutsStore = useLayoutsStore()
const currentLayoutDef = computed(() => layoutsStore.byId[editForm.layout_type] || null)
const currentTypeDef = computed(() => layoutsStore.typeById[currentLayoutDef.value?.type] || null)
// レイアウトの自動差し替え判定と、ギャラリーの「いまの内容で使える」表示に使う件数
const currentItemCount = computed(() => {
  const path = currentTypeDef.value?.collection
  if (!path) return 0
  const node = path.split('.').reduce((acc, key) => (acc ? acc[key] : undefined), slideContent.value)
  return Array.isArray(node) ? node.length : 0
})

// アイコンと色はレイアウト（40 種）ではなく「型」（14 種）に紐づける。
// レイアウトを足しても、その型の見た目をそのまま受け継ぐので追記が要らない。
const TYPE_ICONS = {
  statement: 'mdi-text-short',      list: 'mdi-format-list-bulleted',
  sequence: 'mdi-arrow-right-bold-outline', contrast: 'mdi-compare',
  hierarchy: 'mdi-triangle-outline', cycle: 'mdi-autorenew',
  matrix: 'mdi-view-grid-outline',  sets: 'mdi-circle-multiple-outline',
  table: 'mdi-table',               chart: 'mdi-chart-bar',
  formula: 'mdi-function-variant',  media: 'mdi-image',
  dialog: 'mdi-chat-processing',    cover: 'mdi-format-header-1',
}
const TYPE_COLORS = {
  statement: 'blue-grey', list: 'teal',     sequence: 'indigo',  contrast: 'cyan',
  hierarchy: 'amber',     cycle: 'green',   matrix: 'deep-purple', sets: 'purple',
  table: 'brown',         chart: 'pink',    formula: 'lime',     media: 'blue',
  dialog: 'light-green',  cover: 'orange',
}

function layoutType(id) {
  return layoutsStore.byId[id]?.type || ''
}
function layoutIcon(id) {
  return TYPE_ICONS[layoutType(id)] ?? 'mdi-layers'
}
function layoutLabel(id) {
  return layoutsStore.byId[id]?.label ?? id
}
function layoutColor(id) {
  return TYPE_COLORS[layoutType(id)] ?? 'grey'
}

/**
 * ギャラリーでレイアウトを選んだとき。
 *
 * 同じ型の中なら内容はそのまま使えるので何もしない。
 * 型をまたぐときはサーバー側で移し替え、表示されなくなる件数があれば確認する。
 */
async function handleLayoutSelected(layout) {
  const fromLayout = selectedScene.value?.layout_type || 'text_only'
  if (layoutType(fromLayout) === layout.type) return
  try {
    const { data } = await layoutApi.convert(fromLayout, layout.id, slideContent.value)
    if (data.lost_count > 0) {
      const ok = window.confirm(
        `「${layout.label}」は ${layout.max} 件までのため、${data.lost_count} 件が表示されなくなります。\n` +
        'このまま切り替えますか？（保存するまでは元に戻せます）'
      )
      if (!ok) {
        editForm.layout_type = fromLayout
        return
      }
    }
    slideContent.value = data.content
  } catch (e) {
    ui.notifyError('レイアウトの切り替えに失敗しました: ' + (e.response?.data?.detail || e.message))
    editForm.layout_type = fromLayout
  }
}


// ---- 画像スロットとレイアウトの対応 ----
//
// media 型のレイアウトは画像を「内容」として受け取り、必要枚数を capacity で
// 宣言している（1 枚のものから 4 枚のギャラリーまで）。それ以外の型では
// 素材は絶対配置の添え物なので、従来どおりの既定枠数を出す。

const DEFAULT_ASSET_SLOTS = 3

const isMediaLayout = computed(() => currentLayoutDef.value?.type === 'media')

const assetSlotCount = computed(() => {
  const def = currentLayoutDef.value
  if (!def || def.type !== 'media' || def.any_count) return DEFAULT_ASSET_SLOTS
  return def.max || DEFAULT_ASSET_SLOTS
})

// キャプションはスライド内容 (images[]) が持つ。スロット N が images[N-1] に対応する。
const slotCaptions = computed(() =>
  (Array.isArray(slideContent.value.images) ? slideContent.value.images : [])
    .map((img) => (img && img.caption) || '')
)

function applySlotCaptions(list) {
  if (!Array.isArray(slideContent.value.images)) slideContent.value.images = []
  const images = slideContent.value.images
  list.forEach((caption, idx) => {
    while (images.length <= idx) images.push({ src: '', caption: '' })
    images[idx].caption = caption
  })
}


const speakerOptions = computed(() => {
  const options = [{ title: 'デフォルト (オーバーライドなし)', value: null }]
  speakersStore.speakers.forEach(s => {
    options.push({ title: s.name, value: s.id })
  })
  return options
})

// ナレーション長の推定（14文字 ≒ 1秒）
const estimatedDuration = computed(() => {
  const len = editForm.narration_text?.length ?? 0
  if (len === 0) return 0
  return Math.round(len / 14)
})

const isDummySpeakerSelected = computed(() => {
  const activeSpeakerId = editForm.speaker_id || defaultSpeakerId.value
  if (!activeSpeakerId) return false
  const sp = speakersStore.speakers.find(s => s.id === activeSpeakerId)
  return sp?.is_system && sp?.reference_audio_path?.includes('default/reference.wav')
})

const narrationLengthHint = computed(() => {
  const sec = estimatedDuration.value
  if (sec === 0) return '未入力'
  if (sec < 20) return `約 ${sec} 秒（短め）`
  if (sec <= 35) return `約 ${sec} 秒（適切）`
  return `約 ${sec} 秒（長め）`
})

const narrationChipColor = computed(() => {
  const sec = estimatedDuration.value
  if (sec === 0) return 'default'
  if (sec < 20) return 'warning'
  if (sec <= 35) return 'success'
  return 'error'
})

// 現在実行中の処理名（シーン詳細パネルのステータスインジケーター用）
const processingLabel = computed(() => {
  if (scenesStore.bulkGenLoading) {
    const { done, total, currentTitle } = scenesStore.bulkGenProgress
    return `全シーンの AI 内容を一括生成中... (${done}/${total}${currentTitle ? ' - ' + currentTitle : ''})`
  }
  if (previewLoading.value) {
    const sec = previewElapsedSec.value
    return sec > 0
      ? `音声プレビューを合成中...（バックグラウンド処理、経過 ${sec} 秒）`
      : '音声プレビューを合成中...（バックグラウンド処理）'
  }
  if (narrationGenLoading.value) return 'AIナレーションを生成中...'
  if (contentGenLoading.value) return 'AIスライド内容を生成中...'
  if (saveLoading.value) return 'シーンを保存中...'
  if (scenesStore.loading) return 'シーンデータを更新中...'
  return null
})

const handleGenerateAllContent = async () => {
  try {
    await scenesStore.generateAllContent(videoId, true)
    if (scenesStore.scenes.length) {
      const currentId = selectedScene.value?.id
      const latest = scenesStore.scenes.find(s => s.id === currentId) || scenesStore.scenes[0]
      selectScene(latest)
    }
  } catch (e) {
    // notifyError is handled in store
  }
}

onMounted(async () => {
  // レイアウトのカタログ（型・見せ方・編集フォームの項目定義）。
  // 画面のあちこちで参照するので、シーンを選ぶ前に読み込んでおく。
  await layoutsStore.fetchCatalog()
  await videosStore.fetchOne(videoId)
  await videosStore.fetchStyle(videoId)
  await scenesStore.fetchAll(videoId)
  await speakersStore.fetchAll()
  await generationStore.fetchHistories(videoId)
  await generationStore.fetchGenerationStatus(videoId)
  
  // シナリオの初期読み込み
  await scenarioStore.fetchScenario(videoId)

  defaultSpeakerId.value = videosStore.currentStyle?.default_speaker_id || null
  defaultSpeakerBId.value = videosStore.currentStyle?.default_speaker_b_id || null

  if (scenesStore.scenes.length) {
    selectScene(scenesStore.scenes[0])
  }
})

// シナリオ確定後のコールバック
const onScenarioFinalized = async () => {
  await scenesStore.fetchAll(videoId)
  if (scenesStore.scenes.length) {
    selectScene(scenesStore.scenes[0])
  }
  activeTab.value = 'scenes'
}

// AI ナレーション生成
const generateNarration = async () => {
  if (!selectedScene.value) return

  narrationGenLoading.value = true
  try {
    const { data } = await scenarioApi.generateNarration(selectedScene.value.id)
    editForm.narration_text = data.narration_text
    ui.notify('AI ナレーションを生成しました。')
  } catch (e) {
    ui.notifyError('ナレーション生成に失敗しました: ' + e.message)
  } finally {
    narrationGenLoading.value = false
  }
}

// AI シーン内容（スライド構造＋ナレーション）の生成
const generateSceneContent = async () => {
  if (!selectedScene.value) return

  contentGenLoading.value = true
  try {
    const { data } = await scenarioApi.generateSceneContent(selectedScene.value.id)
    applySlideContentFromScene(data)
    const idx = scenesStore.scenes.findIndex(s => s.id === data.id)
    if (idx !== -1) scenesStore.scenes[idx] = data
    selectedScene.value = data
    ui.notify('AI がシーン内容を生成しました。')
  } catch (e) {
    ui.notifyError('シーン内容の生成に失敗しました: ' + e.message)
  } finally {
    contentGenLoading.value = false
  }
}

function handleAudioLoaded(e) {
  previewAudioDuration.value = e.target.duration
}

watch(selectedScene, () => {
  if (scenesStore.previewAudioUrl) {
    URL.revokeObjectURL(scenesStore.previewAudioUrl)
    scenesStore.previewAudioUrl = ''
  }
  previewAudioDuration.value = 0
})

watch(activeTab, async (newTab) => {
  if (newTab === 'scenario') {
    await scenarioStore.fetchScenario(videoId)
  }
})

onBeforeUnmount(() => {
  generationStore.disconnectWebSocket()
})


function applySlideContentFromScene(scene) {
  if (!scene) return
  editForm.title = scene.title ?? editForm.title
  editForm.layout_type = scene.layout_type || editForm.layout_type
  editForm.narration_text = scene.narration_text || ''
  editForm.outline_summary = scene.outline_summary || editForm.outline_summary

  // 内容はバックエンドが型のスキーマへ正規化済み。画面側でほぐし直さない
  // （ほぐすとレイアウトごとの分岐が復活し、型を増やすたびにここが膨らむ）。
  let parsed = {}
  if (scene.slide_content_json) {
    try {
      parsed = JSON.parse(scene.slide_content_json) || {}
    } catch (e) {
      console.warn('slide_content_json のパースに失敗しました', e)
    }
  }
  rawSlideContent.value = parsed
  slideContent.value = { ...parsed }
}

async function generateImagePrompt() {
  if (!selectedScene.value) return
  imagePromptLoading.value = true
  try {
    const { data } = await scenarioApi.generateImagePrompt(selectedScene.value.id)
    selectedScene.value = data
    const idx = scenesStore.scenes.findIndex(s => s.id === data.id)
    if (idx !== -1) scenesStore.scenes[idx] = data
    applySlideContentFromScene(data)
    ui.notify('画像生成プロンプトを作成しました。')
  } catch (e) {
    ui.notifyError('画像プロンプトの生成に失敗しました: ' + e.message)
  } finally {
    imagePromptLoading.value = false
  }
}

async function copyImagePrompt() {
  const text = selectedScene.value?.image_prompt || ''
  if (!text) return
  try {
    await navigator.clipboard.writeText(text)
    ui.notify('プロンプトをコピーしました。')
  } catch (e) {
    const ta = document.createElement('textarea')
    ta.value = text
    document.body.appendChild(ta)
    ta.select()
    document.execCommand('copy')
    document.body.removeChild(ta)
    ui.notify('プロンプトをコピーしました。')
  }
}

function selectScene(scene) {
  selectedScene.value = scene
  editForm.speaker_id = scene.speaker_id || null
  editForm.speaker_b_id = scene.speaker_b_id || null

  designPrompt.value = ''
  codeEditMode.value = false
  codeHtml.value = ''
  codeCss.value = ''
  codePreviewUrl.value = ''

  applySlideContentFromScene(scene)
}

async function applyDesignAdjust() {
  if (!designPrompt.value.trim() || !selectedScene.value) return
  applyingDesign.value = true
  try {
    await scenesStore.applyDesignAdjust(selectedScene.value.id, designPrompt.value)
    ui.notify('AI によるデザイン調整を適用しました')
    designPrompt.value = ''
    await loadSceneCode()
    await refreshCodePreview()
  } catch (e) {
    ui.notifyError('AIデザイン調整に失敗しました: ' + e.message)
  } finally {
    applyingDesign.value = false
  }
}

async function loadSceneCode() {
  if (!selectedScene.value) return
  const { html, css } = await scenesStore.fetchEffectiveCode(selectedScene.value.id)
  codeHtml.value = html
  codeCss.value = css
}

async function applySceneCode() {
  if (!selectedScene.value) return
  await scenesStore.update(selectedScene.value.id, { custom_html: codeHtml.value, custom_css: codeCss.value })
  ui.notify('コードを保存しました')
  await refreshCodePreview()
}

async function resetSceneCustomCode() {
  if (!selectedScene.value) return
  await scenesStore.update(selectedScene.value.id, { custom_html: null, custom_css: null })
  ui.notify('自動生成に戻しました')
  await loadSceneCode()
  await refreshCodePreview()
}

async function refreshCodePreview() {
  if (!videoId) return
  const { data } = await api.post(`/videos/${videoId}/preview`)
  // preview_url にはプレビュー用フラグとキャッシュ回避のクエリが含まれているため、そのまま使う
  codePreviewUrl.value = data.preview_url
}

async function confirmDeleteHistory(h) {
  const label = formatDate(h.started_at)
  if (!window.confirm(`${label} の生成履歴を削除しますか？（元に戻せません）`)) return
  try {
    await generationStore.remove(h.id)
  } catch (e) {
    ui.notifyError('削除に失敗しました: ' + e.message)
  }
}

async function handleAddScene() {
  const payload = {
    title: '新しいシーン',
    layout_type: 'text_only',
    narration_text: 'ここにナレーションテキストを入力してください。'
  }
  const newScene = await scenesStore.create(videoId, payload)
  selectScene(newScene)
}

async function handleDeleteScene(sceneId) {
  await scenesStore.remove(sceneId)
  if (selectedScene.value?.id === sceneId) {
    if (scenesStore.scenes.length) {
      selectScene(scenesStore.scenes[0])
    } else {
      selectedScene.value = null
    }
  }
}

async function handleSaveScene() {
  if (!selectedScene.value) return
  saveLoading.value = true
  try {
    // レイアウト別の組み立てはしない。フォームが型のスキーマどおりの形を保っている。
    const slideJsonObj = { ...slideContent.value, title: slideContent.value.title ?? editForm.title }

    const payload = {
      title: editForm.title,
      layout_type: editForm.layout_type,
      narration_text: editForm.narration_text,
      speaker_id: editForm.speaker_id,
      speaker_b_id: editForm.speaker_b_id,
      slide_content_json: JSON.stringify(slideJsonObj)
    }

    await scenesStore.update(selectedScene.value.id, payload)
    
    // indexを同期させるため再取得
    await scenesStore.fetchAll(videoId)
    // 選択しなおす
    const updated = scenesStore.scenes.find(s => s.id === selectedScene.value.id)
    if (updated) {
      selectScene(updated)
    }
  } finally {
    saveLoading.value = false
  }
}

async function onDragEnd() {
  // 並び替え処理
  // 変更後のインデックスをAPIに送信
  for (let idx = 0; idx < scenesStore.scenes.length; idx++) {
    const s = scenesStore.scenes[idx]
    if (s.index !== idx + 1) {
      await scenesStore.reorder(s.id, idx + 1)
    }
  }
  await scenesStore.fetchAll(videoId)
}

async function moveIndex(scene, currentIndex, direction) {
  const newIndex = currentIndex + direction + 1 // 1-indexed
  await scenesStore.reorder(scene.id, newIndex)
  await scenesStore.fetchAll(videoId)
}

async function handlePlayPreview() {
  if (!selectedScene.value) return
  if (!selectedScene.value.narration_text?.trim()) {
    previewError.value = 'ナレーションテキストが未入力です。テキストを入力して保存してから再試行してください。'
    return
  }
  previewError.value = null  // 前回のエラーをクリア
  previewElapsedSec.value = 0
  previewLoading.value = true
  try {
    await scenesStore.playPreview(selectedScene.value.id, (sec) => {
      previewElapsedSec.value = sec
    })
  } catch (e) {
    previewError.value = e.message
  } finally {
    previewLoading.value = false
  }
}

async function handleSaveSpeaker() {
  await videosStore.updateStyle(videoId, {
    default_speaker_id: defaultSpeakerId.value,
    default_speaker_b_id: defaultSpeakerBId.value
  })
}

// 生成オプションを選んでから開始する（既定は音声を再利用する高速モード）
function openGenerateDialog() {
  generateOptions.regenerateAudio = false
  generateDialog.value = true
}

async function handleGenerate() {
  generateDialog.value = false
  await generationStore.generate(videoId, generateOptions.regenerateAudio)
}

async function handleResetStatus() {
  if (confirm('動画の生成ステータスを強制リセットしますか？')) {
    await generationStore.resetStatus(videoId)
    await videosStore.fetchVideo(videoId)
  }
}

async function handleSlidePreview() {
  slidePreviewLoading.value = true
  try {
    const { data } = await api.post(`/videos/${videoId}/preview`)
    slidePreviewUrl.value = data.preview_url
    slidePreviewDialog.value = true
  } catch (e) {
    ui.notifyError('プレビューの生成に失敗しました: ' + e.message)
  } finally {
    slidePreviewLoading.value = false
  }
}

function openVideoPlayer(generationId) {
  playerSrc.value = generationStore.playUrl(generationId)
  playerDialog.value = true
}

function statusColor(status) {
  return {
    draft: 'default',
    generating: 'warning',
    completed: 'success',
    failed: 'error',
    running: 'warning'
  }[status] ?? 'default'
}




function formatDate(dateStr) {
  if (!dateStr) return '-'
  const d = new Date(dateStr)
  return d.toLocaleString()
}

function formatBytes(bytes) {
  if (bytes === 0) return '0 Bytes'
  const k = 1024
  const sizes = ['Bytes', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i]
}




// handleAssetsChange は撤去した。
// slideContent.image_src（.value 抜きで Ref 自身に書いていたため元々効いていない）
// への書き戻しをしていたが、image_src は images[] に置き換わった旧キーであり、
// 画像パスの解決は composition.py が素材スロットから直接行っている。
</script>

<style scoped>
.editor-root-container {
  background: #090a14;
}

.editor-top-bar {
  border-bottom: 1px solid rgba(255, 255, 255, 0.07) !important;
}

.editor-title {
  color: #f1f5f9;
  letter-spacing: -0.2px;
}

/* ─── ステッパータブスタイル ─── */
.editor-stepper-tabs {
  border-bottom: 1px solid rgba(255, 255, 255, 0.08) !important;
}
.stepper-tab {
  text-transform: none !important;
  font-weight: 600 !important;
  font-size: 0.85rem !important;
  letter-spacing: 0px !important;
  padding: 0 18px !important;
  min-height: 44px !important;
  transition: all 0.2s ease !important;
}
.step-num {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 18px;
  height: 18px;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.1);
  font-size: 0.65rem;
  margin-right: 6px;
  color: rgba(255, 255, 255, 0.7);
}
:deep(.v-tab--selected) .step-num {
  background: #06b6d4;
  color: #090a14;
  font-weight: 800;
  box-shadow: 0 0 8px #06b6d4;
}

/* ─── AI 専用ネオンボタン ─── */
.btn-neon-ai {
  background: linear-gradient(135deg, #06b6d4 0%, #a855f7 100%) !important;
  color: #ffffff !important;
  font-weight: 700 !important;
  border: none !important;
  box-shadow: 0 2px 10px rgba(6, 182, 212, 0.35) !important;
  transition: all 0.2s ease !important;
}
.btn-neon-ai:hover {
  box-shadow: 0 4px 16px rgba(168, 85, 247, 0.5) !important;
  transform: translateY(-1px);
}

/* ─── タイムライン & シーン一覧 ─── */
.cyber-scenes-col {
  border-right: 1px solid rgba(255, 255, 255, 0.06) !important;
  background: rgba(12, 14, 26, 0.4);
}
.cyber-scenes-list-container {
  background: rgba(9, 10, 20, 0.5);
}

.cursor-grab {
  cursor: grab;
}
.cursor-grab:active {
  cursor: grabbing;
}

/* シーンサムネイル */
.scene-thumb {
  width: 42px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 6px;
  box-shadow: 0 2px 6px rgba(0, 0, 0, 0.4);
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
}

.thumb-text_only             { background: linear-gradient(135deg, #475569 0%, #64748b 100%); }
.thumb-text_left_image_right { background: linear-gradient(135deg, #0284c7 0%, #38bdf8 100%); }
.thumb-full_image            { background: linear-gradient(135deg, #7c3aed 0%, #c084fc 100%); }
.thumb-bullet_list           { background: linear-gradient(135deg, #0d9488 0%, #2dd4bf 100%); }
.thumb-section_header        { background: linear-gradient(135deg, #ea580c 0%, #fb923c 100%); }
.thumb-comparison            { background: linear-gradient(135deg, #0891b2 0%, #22d3ee 100%); }
.thumb-chat_dialog           { background: linear-gradient(135deg, #16a34a 0%, #4ade80 100%); }

.min-width-0 { min-width: 0; }

.editor-logo-img {
  width: 26px;
  height: 26px;
  object-fit: cover;
  border-radius: 8px;
  border: 1px solid rgba(255, 255, 255, 0.2);
  box-shadow: 0 2px 8px rgba(6, 182, 212, 0.4);
}

.status-pulse-dot {
  display: inline-block;
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background-color: #fbbf24;
  box-shadow: 0 0 6px #fbbf24;
  animation: pulse 1.5s infinite;
}
</style>
