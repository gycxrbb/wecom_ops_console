export const CRM_DEMO_URL = 'https://crm.mengfugui.com'

export const createTemplateCardExample = (cardType: 'text_notice' | 'news_notice' = 'text_notice') => {
  if (cardType === 'news_notice') {
    return {
      template_card: {
        card_type: 'news_notice',
        source: {
          icon_url: 'https://picsum.photos/seed/wecom-card-icon/96/96',
          desc: '训练营运营台',
          desc_color: 0,
        },
        main_title: {
          title: '惯能 H5 学习卡',
          desc: '打开 CRM H5 查看今日内容，并在群里完成打卡反馈',
        },
        card_image: {
          url: 'https://picsum.photos/seed/guanneng-h5-cover/960/720',
          aspect_ratio: 1.3,
        },
        image_text_area: {
          type: 1,
          url: CRM_DEMO_URL,
          title: '惯能 H5 · 今日主题讲解',
          desc: '适合放运营每天要发的课程页、活动页或内容页，运营同学直接改标题和说明就能复用。',
          image_url: 'https://picsum.photos/seed/guanneng-h5-thumb/240/240',
        },
        quote_area: {
          type: 1,
          url: CRM_DEMO_URL,
          title: '运营提示',
          quote_text: '如果今天主要是引导用户看内容页、进 H5 或跳 CRM，这种图文展示模板卡片最直观。',
        },
        vertical_content_list: [
          { title: '内容主题', desc: '惯能 H5 页面导读' },
          { title: '建议动作', desc: '先阅读，再回群里回复一句今日行动' },
          { title: '打开入口', desc: 'CRM 内容页' },
        ],
        horizontal_content_list: [
          { keyname: '群名称', value: '测试群' },
          { keyname: '负责人', value: 'admin' },
        ],
        jump_list: [
          { type: 1, title: '查看图文详情', url: CRM_DEMO_URL },
          { type: 1, title: '打开 CRM', url: CRM_DEMO_URL },
        ],
        card_action: {
          type: 1,
          url: CRM_DEMO_URL,
        },
      },
    }
  }

  return {
    template_card: {
      card_type: 'text_notice',
      source: {
        icon_url: 'https://picsum.photos/seed/wecom-card-icon/96/96',
        desc: '训练营运营台',
        desc_color: 0,
      },
      main_title: {
        title: '今晚 20:00 晚总结提醒',
        desc: '请在 20:30 前完成今日复盘',
      },
      emphasis_content: {
        title: '20:30',
        desc: '提交截止',
      },
      sub_title_text: '建议按“执行动作 / 最大卡点 / 明日调整”三段提交，方便教练统一点评。',
      quote_area: {
        type: 1,
        url: `${CRM_DEMO_URL}/tips`,
        title: '填写建议',
        quote_text: '先写今天最稳定做到的一件事，再写最想优化的一件事。',
      },
      horizontal_content_list: [
        { keyname: '群名称', value: '测试群' },
        { keyname: '负责人', value: 'admin' },
        { keyname: '截止时间', value: '今天 20:30' },
      ],
      jump_list: [
        { type: 1, title: '查看详情', url: CRM_DEMO_URL },
        { type: 1, title: '提交反馈', url: CRM_DEMO_URL },
      ],
      card_action: {
        type: 1,
        url: CRM_DEMO_URL,
      },
    },
  }
}

export const templateCardExampleVariables = {
  text_notice: {},
  news_notice: {},
}
