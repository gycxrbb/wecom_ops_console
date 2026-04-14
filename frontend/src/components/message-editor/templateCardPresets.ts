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
          title: '{{ title }}',
          desc: '{{ desc }}',
        },
        card_image: {
          url: '{{ card_image_url }}',
          aspect_ratio: 1.3,
        },
        image_text_area: {
          type: 1,
          url: '{{ detail_url }}',
          title: '{{ image_text_title }}',
          desc: '{{ image_text_desc }}',
          image_url: '{{ image_url }}',
        },
        quote_area: {
          type: 1,
          url: '{{ quote_url }}',
          title: '{{ quote_title }}',
          quote_text: '{{ quote_text }}',
        },
        vertical_content_list: [
          { title: '适用人群', desc: '{{ audience }}' },
          { title: '执行动作', desc: '{{ action }}' },
          { title: '截止时间', desc: '{{ deadline }}' },
        ],
        horizontal_content_list: [
          { keyname: '群名称', value: '{{ group_name }}' },
          { keyname: '负责人', value: '{{ coach_name }}' },
        ],
        jump_list: [
          { type: 1, title: '查看图文详情', url: '{{ detail_url }}' },
          { type: 1, title: '打开反馈表', url: '{{ form_url }}' },
        ],
        card_action: {
          type: 1,
          url: '{{ detail_url }}',
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
        title: '{{ title }}',
        desc: '{{ desc }}',
      },
      emphasis_content: {
        title: '{{ emphasis_title }}',
        desc: '{{ emphasis_desc }}',
      },
      sub_title_text: '{{ subtitle }}',
      quote_area: {
        type: 1,
        url: '{{ quote_url }}',
        title: '{{ quote_title }}',
        quote_text: '{{ quote_text }}',
      },
      horizontal_content_list: [
        { keyname: '群名称', value: '{{ group_name }}' },
        { keyname: '负责人', value: '{{ coach_name }}' },
        { keyname: '截止时间', value: '{{ deadline }}' },
      ],
      jump_list: [
        { type: 1, title: '查看详情', url: '{{ detail_url }}' },
        { type: 1, title: '提交反馈', url: '{{ form_url }}' },
      ],
      card_action: {
        type: 1,
        url: '{{ detail_url }}',
      },
    },
  }
}

export const templateCardExampleVariables = {
  text_notice: {
    title: '今晚 20:00 晚总结提醒',
    desc: '请在 20:30 前完成今日复盘',
    subtitle: '建议按“执行动作 / 最大卡点 / 明日调整”三段提交，方便教练统一点评。',
    emphasis_title: '20:30',
    emphasis_desc: '提交截止',
    deadline: '今天 20:30',
    quote_title: '填写建议',
    quote_text: '先写今天最稳定做到的一件事，再写最想优化的一件事。',
    quote_url: 'https://example.com/tips',
    detail_url: 'https://example.com/daily-summary',
    form_url: 'https://example.com/summary-form',
  },
  news_notice: {
    title: '今日学习卡已更新',
    desc: '3 分钟看完这张图，再去群里打卡',
    card_image_url: 'https://picsum.photos/seed/wecom-card-cover/960/720',
    image_text_title: '餐后走 10 分钟，为什么比“硬扛少吃”更稳？',
    image_text_desc: '这张图把“餐后波动、饱腹感、执行难度”三件事放到一张图里讲清楚。',
    image_url: 'https://picsum.photos/seed/wecom-card-inline/240/240',
    detail_url: 'https://example.com/lesson-card',
    quote_title: '运营建议',
    quote_text: '如果群里今天执行率偏低，优先发图文展示模板卡片，运营同学更容易直接复用。',
    quote_url: 'https://example.com/ops-guide',
    audience: '今天没来得及看长文的营员',
    action: '看图 3 分钟后，在群里回复一句“我今天准备怎么做”',
    deadline: '今天 21:00 前',
    form_url: 'https://example.com/checkin',
  },
}
