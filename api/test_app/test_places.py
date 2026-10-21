"""
Real places in Finland for the random test rides made in the admin (see
RideAdmin.generate_test_rides), as (name, postcode, lat, lng) of the town or
city centre. Most are around the LUT campuses, with the bigger cities further
away for longer rides.
"""
PLACES = [
    # South Karelia
    ("Lappeenranta", "53100", 61.0587, 28.1887),
    ("Imatra", "55100", 61.1719, 28.7526),
    ("Taipalsaari", "54920", 61.1586, 28.0558),
    ("Lemi", "54710", 61.0617, 27.8045),
    ("Luumäki", "54500", 60.9200, 27.5690),
    ("Ruokolahti", "56100", 61.2913, 28.8240),
    ("Rautjärvi", "56800", 61.4310, 29.3670),
    ("Parikkala", "59100", 61.5500, 29.5000),
    # Kymenlaakso
    ("Kouvola", "45100", 60.8679, 26.7042),
    ("Kotka", "48100", 60.4664, 26.9458),
    ("Hamina", "49400", 60.5697, 27.1981),
    ("Miehikkälä", "49700", 60.6710, 27.6990),
    ("Virolahti", "49900", 60.5810, 27.7090),
    # Päijät-Häme
    ("Lahti", "15110", 60.9827, 25.6612),
    ("Hollola", "15870", 60.9890, 25.5150),
    ("Nastola", "15560", 60.9480, 25.9310),
    ("Orimattila", "16300", 60.8040, 25.7290),
    ("Heinola", "18100", 61.2056, 26.0381),
    # South Savo
    ("Mikkeli", "50100", 61.6886, 27.2723),
    ("Savonlinna", "57130", 61.8687, 28.8786),
    ("Pieksämäki", "76100", 62.3003, 27.1590),
    ("Varkaus", "78200", 62.3155, 27.8732),
    # Uusimaa
    ("Helsinki", "00100", 60.1710, 24.9414),
    ("Espoo", "02100", 60.1757, 24.8050),
    ("Vantaa", "01300", 60.2925, 25.0440),
    ("Porvoo", "06100", 60.3932, 25.6650),
    ("Loviisa", "07900", 60.4569, 26.2250),
    ("Kerava", "04200", 60.4034, 25.1050),
    ("Järvenpää", "04400", 60.4737, 25.0899),
    ("Hyvinkää", "05800", 60.6305, 24.8580),
    # Further away
    ("Hämeenlinna", "13100", 60.9959, 24.4643),
    ("Tampere", "33100", 61.4981, 23.7610),
    ("Turku", "20100", 60.4510, 22.2670),
    ("Jyväskylä", "40100", 62.2426, 25.7473),
    ("Kuopio", "70100", 62.8924, 27.6770),
    ("Joensuu", "80100", 62.6010, 29.7636),
    ("Iisalmi", "74100", 63.5592, 27.1907),
    ("Pori", "28100", 61.4851, 21.7974),
    ("Seinäjoki", "60100", 62.7903, 22.8403),
    ("Oulu", "90100", 65.0121, 25.4651),
]
